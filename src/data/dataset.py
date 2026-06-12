"""
PyTorch Dataset built from the manifest CSV.

Each row -> (PIL.Image, label_id). Image transforms applied per split.
Multi-page TIFF: takes frame 0. Grayscale fingerprints converted to RGB.

Robust to corrupt images: a single bad file does NOT crash training.
Bad paths are reported once on stderr; if a file fails repeatedly,
we fall back to the next valid index within the same dataset.
"""
from __future__ import annotations

import sys

import pandas as pd
from PIL import Image, ImageFile
from torch.utils.data import Dataset, DataLoader

from src import config as C
from src.data.transforms import train_transform, eval_transform


# Allow PIL to load truncated / partially-written images instead of crashing.
# Many "broken data stream" errors in LivDet come from JPEGs missing the
# final marker — they're still usable for training.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Lift the DecompressionBomb warning ceiling (LivDet has some big TIFFs).
Image.MAX_IMAGE_PIXELS = None

# Reported once per bad path to keep logs short
_REPORTED_BAD_PATHS: set[str] = set()


class FingerprintDataset(Dataset):
    def __init__(self, manifest_df: pd.DataFrame, split: str,
                 transform=None, max_retries: int = 5):
        assert split in {"train", "val", "test"}, split
        self.df = manifest_df[manifest_df["split"] == split].reset_index(drop=True)
        self.transform = transform
        self.max_retries = max_retries

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx: int):
        # Retry with the next index on any image-load failure.
        for attempt in range(self.max_retries):
            try_idx = (idx + attempt) % len(self.df)
            row = self.df.iloc[try_idx]
            try:
                img = self._load_image(row["file_path"])
            except Exception as e:
                self._report_bad(row["file_path"], e)
                continue
            try:
                if self.transform:
                    img = self.transform(img)
            except Exception as e:
                self._report_bad(row["file_path"], e)
                continue
            return img, int(row["label_id"])

        raise RuntimeError(
            f"Could not load any image starting from idx={idx} "
            f"after {self.max_retries} retries. Check your manifest."
        )

    @staticmethod
    def _load_image(path: str) -> Image.Image:
        img = Image.open(path)
        try:
            img.seek(0)        # multi-page TIFF -> first frame
        except Exception:
            pass
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Force-decode here so PIL errors raise inside __getitem__,
        # not later inside the transform pipeline.
        img.load()
        return img

    @staticmethod
    def _report_bad(path: str, err: Exception):
        if path in _REPORTED_BAD_PATHS:
            return
        _REPORTED_BAD_PATHS.add(path)
        print(f"[dataset] skipping bad image: {path}  ({type(err).__name__}: {err})",
              file=sys.stderr)


def load_manifest(quick_samples: int | None = None) -> pd.DataFrame:
    csv = C.MANIFEST_DIR / "manifest_v1.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Manifest not found at {csv}. Run: python -m src.data.manifest"
        )
    df = pd.read_csv(csv)
    if quick_samples:
        # Take a balanced sample from each split for quick sanity checking
        parts = []
        for split in ("train", "val", "test"):
            sub = df[df["split"] == split]
            n = min(quick_samples // 3, len(sub))
            parts.append(sub.groupby("label").head(max(1, n // 2)))
        df = pd.concat(parts).reset_index(drop=True)
        print(f"[quick mode] using {len(df)} samples")
    return df


def make_dataloaders(batch_size: int = C.BATCH_SIZE,
                     num_workers: int = C.NUM_WORKERS,
                     quick_samples: int | None = C.QUICK_SAMPLES):
    df = load_manifest(quick_samples)
    common = dict(batch_size=batch_size, num_workers=num_workers,
                  pin_memory=True, persistent_workers=num_workers > 0)
    train_loader = DataLoader(
        FingerprintDataset(df, "train", train_transform()),
        shuffle=True, drop_last=True, **common,
    )
    val_loader = DataLoader(
        FingerprintDataset(df, "val", eval_transform()),
        shuffle=False, **common,
    )
    test_loader = DataLoader(
        FingerprintDataset(df, "test", eval_transform()),
        shuffle=False, **common,
    )
    return train_loader, val_loader, test_loader, df

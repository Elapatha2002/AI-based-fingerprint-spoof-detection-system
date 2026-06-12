"""
Build a manifest CSV from the Normalized/ folder.

Parses each filename `{year}_{sensor}_{material?}_{original}.{ext}` and
records (file_path, split, label, year, sensor, material) into one CSV.

This is the single source of truth for all training/eval scripts.
Run once after normalization. Re-run if you add more data.

Usage:
    python -m src.data.manifest

Output:
    src/data/manifests/manifest_v1.csv
    src/data/manifests/splits_v1.json  (stratified train/val from the train pool)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config as C


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

# Filename forms:
#   live  : {year}_{sensor}_{original}.{ext}
#   spoof : {year}_{sensor}_{material}_{original}.{ext}
NAME_RE = re.compile(
    r"^(?P<year>\d{4})_(?P<sensor>[A-Za-z0-9]+)_(?P<rest>.+)$"
)


def parse_filename(filename: str, label: str) -> dict:
    """Pull (year, sensor, material) from a normalized filename."""
    stem = Path(filename).stem
    m = NAME_RE.match(stem)
    if not m:
        return {"year": None, "sensor": None, "material": None}

    year = m.group("year")
    sensor = m.group("sensor")
    rest = m.group("rest")

    material = None
    if label == "spoof":
        # First token of rest is the material (Silicone, Latex, …)
        material = rest.split("_", 1)[0]

    return {"year": year, "sensor": sensor, "material": material}


def walk_split(split_dir: Path, split_name: str) -> list[dict]:
    """Walk a {split}/{label}/ subtree and return one row per image."""
    rows = []
    for label in ("live", "spoof"):
        d = split_dir / label
        if not d.exists():
            continue
        for fp in d.iterdir():
            if not fp.is_file() or fp.suffix.lower() not in IMAGE_EXTS:
                continue
            meta = parse_filename(fp.name, label)
            rows.append({
                "file_path": str(fp.resolve()),
                "filename": fp.name,
                "split_source": split_name,        # LivDet official: 'train' or 'test'
                "label": label,
                "label_id": C.LABEL_MAP[label],
                "year": meta["year"],
                "sensor": meta["sensor"],
                "material": meta["material"] or ("live" if label == "live" else "unknown"),
            })
    return rows


def build_manifest() -> pd.DataFrame:
    print(f"Walking {C.TRAIN_DIR} ...")
    train_rows = walk_split(C.TRAIN_DIR, "train")
    print(f"  found {len(train_rows):,} images")

    print(f"Walking {C.TEST_DIR} ...")
    test_rows = walk_split(C.TEST_DIR, "test")
    print(f"  found {len(test_rows):,} images")

    df = pd.DataFrame(train_rows + test_rows)
    return df


def make_stratified_split(df: pd.DataFrame, seed: int = C.SEED) -> dict:
    """
    Take the official 'train' pool and split into 85% train / 15% val,
    stratified by (label, sensor, material). The official 'test' split is held out.

    Returns: dict with index lists keyed by 'train', 'val', 'test'.
    """
    test_idx = df.index[df["split_source"] == "test"].tolist()
    trainval = df[df["split_source"] == "train"].copy()

    # Build a composite stratification key, fallback to label if a key class is too rare
    trainval["_strat"] = (trainval["label"] + "|" + trainval["sensor"].fillna("?")
                          + "|" + trainval["material"].fillna("?"))
    counts = trainval["_strat"].value_counts()
    rare = counts[counts < 2].index
    trainval.loc[trainval["_strat"].isin(rare), "_strat"] = trainval["label"]

    tr_idx, val_idx = train_test_split(
        trainval.index.tolist(),
        test_size=C.VAL_FRACTION,
        stratify=trainval["_strat"],
        random_state=seed,
    )

    return {"train": tr_idx, "val": val_idx, "test": test_idx}


def summarize(df: pd.DataFrame, splits: dict) -> None:
    print("\n" + "=" * 60)
    print("MANIFEST SUMMARY")
    print("=" * 60)
    for split_name, idx in splits.items():
        sub = df.loc[idx]
        live = (sub["label"] == "live").sum()
        spoof = (sub["label"] == "spoof").sum()
        total = len(sub)
        print(f"\n  {split_name:6s}  total {total:>6,}   "
              f"live {live:>6,}   spoof {spoof:>6,}   "
              f"ratio {live/total:.3f}")
        years = sub["year"].value_counts().to_dict()
        sensors = sub["sensor"].value_counts().to_dict()
        print(f"           years: {years}")
        print(f"           sensors: {sensors}")


def main():
    df = build_manifest()
    splits = make_stratified_split(df)

    df.loc[splits["train"], "split"] = "train"
    df.loc[splits["val"], "split"] = "val"
    df.loc[splits["test"], "split"] = "test"

    out_csv = C.MANIFEST_DIR / "manifest_v1.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}  ({len(df):,} rows)")

    out_json = C.MANIFEST_DIR / "splits_v1.json"
    with out_json.open("w") as f:
        json.dump({k: [int(i) for i in v] for k, v in splits.items()}, f)
    print(f"Wrote {out_json}")

    summarize(df, splits)


if __name__ == "__main__":
    main()

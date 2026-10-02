"""Create and upload the fixed v1 SHAP background distribution.

Run from the repository root after configuring the private Supabase S3 values
in .env.supabase:

    python tools/prepare_shap_background.py --dry-run
    python tools/prepare_shap_background.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.storage import get_storage  # noqa: E402
from src import config as C  # noqa: E402
from src.xai.shap_background import DEFAULT_PREFIX  # noqa: E402


# Four live and four spoof strata cover every LivDet year while varying sensor
# and attack material. Selection within each stratum is deterministic.
STRATA = (
    {"label": "live", "year": 2009, "sensor": "Biometrika", "material": "live"},
    {"label": "live", "year": 2011, "sensor": "Digital", "material": "live"},
    {"label": "live", "year": 2013, "sensor": "Swipe", "material": "live"},
    {"label": "live", "year": 2015, "sensor": "GreenBit", "material": "live"},
    {"label": "spoof", "year": 2009, "sensor": "Biometrika", "material": "Silicone"},
    {"label": "spoof", "year": 2011, "sensor": "Italdata", "material": "Gelatin"},
    {"label": "spoof", "year": 2013, "sensor": "CrossMatch", "material": "BodyDouble"},
    {"label": "spoof", "year": 2015, "sensor": "DigitalPersona", "material": "Ecoflex"},
)


def _digest_rank(filename: str) -> str:
    return hashlib.sha256(f"fsd-xai-shap-background-v1|{filename}".encode()).hexdigest()


def _select_rows(manifest: pd.DataFrame) -> list[dict]:
    train = manifest[manifest["split"].eq("train")].copy()
    selected: list[dict] = []
    for stratum in STRATA:
        candidates = train
        for column, value in stratum.items():
            candidates = candidates[candidates[column].eq(value)]
        if candidates.empty:
            raise RuntimeError(f"No training sample matches stratum: {stratum}")
        candidates = candidates.copy()
        candidates["_rank"] = candidates["filename"].map(_digest_rank)
        candidates = candidates.sort_values(["_rank", "filename"])
        chosen = None
        for _, row in candidates.iterrows():
            source = Path(row["file_path"])
            if source.is_file():
                chosen = row.to_dict()
                break
        if chosen is None:
            raise RuntimeError(f"No readable file matches stratum: {stratum}")
        selected.append(chosen)
    return selected


def _normalized_png(source: Path) -> bytes:
    with Image.open(source) as image:
        image.seek(0)
        image.load()
        rgb = image.convert("RGB")
    output = io.BytesIO()
    rgb.save(output, format="PNG", optimize=True)
    return output.getvalue()


def build_payload(prefix: str) -> tuple[list[tuple[str, bytes]], dict]:
    manifest_path = C.MANIFEST_DIR / "manifest_v1.csv"
    source_manifest_bytes = manifest_path.read_bytes()
    selected = _select_rows(pd.read_csv(manifest_path))
    objects: list[tuple[str, bytes]] = []
    entries = []
    for position, row in enumerate(selected, start=1):
        source = Path(row["file_path"])
        data = _normalized_png(source)
        safe_sensor = str(row["sensor"]).replace(" ", "-")
        key = (
            f"{prefix}/{position:02d}_{row['label']}_{int(row['year'])}_"
            f"{safe_sensor}.png"
        )
        objects.append((key, data))
        entries.append({
            "position": position,
            "object_key": key,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "source_filename": str(row["filename"]),
            "label": str(row["label"]),
            "year": int(row["year"]),
            "sensor": str(row["sensor"]),
            "material": str(row["material"]),
            "split": "train",
        })
    manifest = {
        "schema_version": 1,
        "background_version": "v1",
        "prefix": prefix,
        "selection_method": "fixed stratified deterministic SHA-256 ranking",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256": hashlib.sha256(source_manifest_bytes).hexdigest(),
        "count": len(entries),
        "images": entries,
    }
    return objects, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    prefix = args.prefix.strip().strip("/")
    if not prefix or ".." in prefix.split("/"):
        parser.error("--prefix must be a safe relative storage prefix")

    objects, manifest = build_payload(prefix)
    print("Fixed SHAP background selection:")
    for entry in manifest["images"]:
        print(
            f"  {entry['position']:02d} {entry['label']:5s} "
            f"{entry['year']} {entry['sensor']:15s} {entry['material']:10s} "
            f"{entry['source_filename']}"
        )
    if args.dry_run:
        print("Dry run complete; nothing was uploaded.")
        return 0

    storage = get_storage()
    ok, message = storage.health_check()
    if not ok:
        raise RuntimeError(f"Private storage check failed: {message}")
    manifest_key = f"{prefix}/manifest.json"
    if storage.object_exists(manifest_key) and not args.replace:
        raise RuntimeError(
            f"{manifest_key} already exists. Use a new versioned prefix or --replace."
        )

    for key, data in objects:
        storage.upload_bytes(key, data, "image/png")
        if hashlib.sha256(storage.download_bytes(key)).hexdigest() != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f"Upload verification failed for {key}")
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    storage.upload_bytes(manifest_key, manifest_bytes, "application/json")
    if storage.download_bytes(manifest_key) != manifest_bytes:
        raise RuntimeError("Upload verification failed for the SHAP background manifest")
    print(f"Uploaded and verified {len(objects)} private images plus {manifest_key}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""
Validate every image in manifest_v1.csv. Rewrite the manifest with only
files that decode successfully. Run this once after the first training crash
so subsequent runs are bulletproof.

Usage:
    python -m src.data.validate
    python -m src.data.validate --workers 8     # parallel scan

Output:
    Overwrites src/data/manifests/manifest_v1.csv (clean rows only)
    Backs up the original to manifest_v1.before_validate.csv
    Writes a bad-files report to results/bad_images_<timestamp>.csv
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
from PIL import Image, ImageFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config as C


# Same robustness flags as the runtime Dataset
ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None


def probe(path: str) -> tuple[str, bool, str]:
    """Try to decode an image end-to-end. Returns (path, ok, reason)."""
    try:
        img = Image.open(path)
        try:
            img.seek(0)
        except Exception:
            pass
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.load()                 # force-decode
        w, h = img.size
        if w < 16 or h < 16:
            return path, False, f"too-small {w}x{h}"
        return path, True, ""
    except Exception as e:
        return path, False, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel I/O threads (4–8 is good on SSD).")
    args = parser.parse_args()

    csv = C.MANIFEST_DIR / "manifest_v1.csv"
    if not csv.exists():
        sys.exit(f"Manifest not found: {csv}\n"
                 f"Run: python -m src.data.manifest")

    df = pd.read_csv(csv)
    print(f"Validating {len(df):,} images with {args.workers} threads ...")

    t0 = time.time()
    results: list[tuple[str, bool, str]] = []
    last_print = t0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, p): p for p in df["file_path"].tolist()}
        for i, fut in enumerate(as_completed(futures), start=1):
            results.append(fut.result())
            if time.time() - last_print > 5:
                elapsed = time.time() - t0
                print(f"  scanned {i:,}/{len(futures):,}  "
                      f"({i / elapsed:.0f} imgs/s, {elapsed:.0f}s)")
                last_print = time.time()

    elapsed = time.time() - t0
    print(f"Scan done in {elapsed:.0f}s")

    res_df = pd.DataFrame(results, columns=["file_path", "ok", "reason"])
    bad = res_df[~res_df["ok"]].copy()
    good_paths = set(res_df.loc[res_df["ok"], "file_path"])

    print(f"\n  GOOD: {res_df['ok'].sum():,}")
    print(f"  BAD : {len(bad):,}")
    if not bad.empty:
        print("\n  Sample of bad files:")
        for _, r in bad.head(10).iterrows():
            print(f"    {r['file_path']}  →  {r['reason']}")
        if len(bad) > 10:
            print(f"    ... and {len(bad) - 10:,} more")

    if bad.empty:
        print("\nAll images valid. Manifest unchanged.")
        return

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bad_csv = C.RESULTS_DIR / f"bad_images_{ts}.csv"
    bad.to_csv(bad_csv, index=False)
    print(f"\nBad-files report → {bad_csv}")

    # Backup original manifest and rewrite without bad rows
    backup = C.MANIFEST_DIR / "manifest_v1.before_validate.csv"
    csv.rename(backup)
    print(f"Backed up original manifest → {backup}")

    clean = df[df["file_path"].isin(good_paths)].copy()
    clean.to_csv(csv, index=False)
    print(f"Rewrote {csv}  ({len(clean):,} rows)")

    print("\nDone. Re-run training:")
    print("    python -m src.training.train --epochs 15")


if __name__ == "__main__":
    main()

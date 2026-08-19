"""
External-dataset validation for the winning FSD-CBAM v2 checkpoint.

Runs inference on a folder of images whose ground-truth label is known
a priori (all-live for a bona-fide dataset such as SOCOFing/Real; all-
spoof for a spoof-only dataset). Reports the operationally-relevant
error rate:

    BPCER  = fraction of bona-fide images misclassified as spoof
    APCER  = fraction of spoof     images misclassified as live

Emits a JSON report to `results/external_<tag>_<timestamp>.json` and
prints a summary block for direct copy-paste into the thesis.

Usage examples:

    # SOCOFing Real (6,000 bona-fide fingerprints, no spoofs)
    python scripts/external_validation.py \\
        --folder "DataSet/SOCOFing/Real" \\
        --label live \\
        --tag socofing_real

    # A hypothetical spoof-only dataset
    python scripts/external_validation.py \\
        --folder "DataSet/SomeSpoofDataset" \\
        --label spoof \\
        --tag some_spoof

The script uses the same preprocessing pipeline as the trained model
(224 x 224 resize, RGB, ImageNet normalisation).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageFile

# Tolerate truncated images the way the training pipeline did
ImageFile.LOAD_TRUNCATED_IMAGES = True

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.factory import get_model
from src.xai.base import preprocess


DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parents[1]
    / "checkpoints" / "fsd_cbam_v2_20260810_122231" / "best.pth"
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def collect_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def load_model(checkpoint: Path, model_name: str, device: torch.device):
    print(f"Loading {model_name} from {checkpoint.name} ...")
    model = get_model(model_name, pretrained=False).to(device)
    state = torch.load(checkpoint, map_location=device, weights_only=False)
    sd = state["model_state"] if isinstance(state, dict) and "model_state" in state else state
    model.load_state_dict(sd)
    model.eval()
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, type=Path,
                    help="Folder of images to evaluate (recursively).")
    ap.add_argument("--label", required=True, choices=["live", "spoof"],
                    help="Ground-truth label for every image in the folder.")
    ap.add_argument("--tag", required=True,
                    help="Short tag used in the output JSON filename.")
    ap.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    ap.add_argument("--model", default="fsd_cbam")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="Decision threshold on P(spoof). Default 0.5.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Optional cap on number of images (useful for smoke tests).")
    args = ap.parse_args()

    if not args.folder.exists():
        sys.exit(f"Folder does not exist: {args.folder}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    model = load_model(args.checkpoint, args.model, device)

    files = collect_images(args.folder)
    if args.limit:
        files = files[:args.limit]
    if not files:
        sys.exit(f"No images found under {args.folder}")

    print(f"Evaluating {len(files):,} images "
           f"(ground truth: {args.label.upper()}) ...")

    y_prob: list[float] = []
    y_pred_spoof = 0
    failed = 0
    t0 = time.time()

    for i, path in enumerate(files):
        try:
            img = Image.open(path).convert("RGB")
            tensor = preprocess(img).to(device)
            with torch.inference_mode():
                logit = model(tensor).item()
            p_spoof = 1.0 / (1.0 + np.exp(-logit))
            y_prob.append(p_spoof)
            if p_spoof >= args.threshold:
                y_pred_spoof += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [WARN] failed on {path.name}: {e}")

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            print(f"  ... {i + 1}/{len(files)}  ({elapsed:.0f}s)")

    n_ok = len(y_prob)
    n_pred_spoof = y_pred_spoof
    n_pred_live = n_ok - n_pred_spoof

    if args.label == "live":
        # BPCER — bona-fide misclassified as spoof
        bpcer = 100.0 * n_pred_spoof / max(n_ok, 1)
        error_metric = ("BPCER", bpcer)
        correct = n_pred_live
    else:
        # APCER — spoof misclassified as live
        apcer = 100.0 * n_pred_live / max(n_ok, 1)
        error_metric = ("APCER", apcer)
        correct = n_pred_spoof

    accuracy = 100.0 * correct / max(n_ok, 1)

    # Simple distribution summary of the probability output
    y = np.array(y_prob) if y_prob else np.array([0.0])
    prob_summary = {
        "mean":   float(y.mean()),
        "median": float(np.median(y)),
        "p05":    float(np.percentile(y, 5)),
        "p95":    float(np.percentile(y, 95)),
        "min":    float(y.min()),
        "max":    float(y.max()),
    }

    elapsed_total = time.time() - t0
    report = {
        "tag":             args.tag,
        "folder":          str(args.folder),
        "checkpoint":      str(args.checkpoint),
        "model":           args.model,
        "threshold":       args.threshold,
        "ground_truth":    args.label,
        "n_total_found":   len(files),
        "n_evaluated":     n_ok,
        "n_failed":        failed,
        "n_pred_live":     n_pred_live,
        "n_pred_spoof":    n_pred_spoof,
        "accuracy_pct":    accuracy,
        "error_metric":    error_metric[0],
        "error_value_pct": error_metric[1],
        "prob_summary":    prob_summary,
        "elapsed_seconds": elapsed_total,
        "timestamp":       datetime.now().isoformat(timespec="seconds"),
    }

    results_dir = Path(__file__).resolve().parents[1] / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"external_{args.tag}_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print()
    print("=" * 60)
    print(f"External validation — {args.tag}")
    print("=" * 60)
    print(f"  Ground truth      : {args.label.upper()}")
    print(f"  Images evaluated  : {n_ok:,}  (failed: {failed})")
    print(f"  Predicted LIVE    : {n_pred_live:,}")
    print(f"  Predicted SPOOF   : {n_pred_spoof:,}")
    print(f"  Accuracy          : {accuracy:.2f}%")
    print(f"  {error_metric[0]}             : {error_metric[1]:.2f}%")
    print(f"  P(spoof) summary  : median={prob_summary['median']:.3f}  "
           f"mean={prob_summary['mean']:.3f}  "
           f"p05-p95=[{prob_summary['p05']:.3f}, {prob_summary['p95']:.3f}]")
    print(f"  Wall clock        : {elapsed_total:.0f}s")
    print(f"  Report            : {out_path}")


if __name__ == "__main__":
    main()

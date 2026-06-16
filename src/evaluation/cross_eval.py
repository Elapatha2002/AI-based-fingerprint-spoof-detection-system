"""
Cross-sensor / cross-material / cross-year evaluation.

Loads a trained checkpoint, runs inference on the full test set once,
then slices the predictions by metadata to answer:

  1. Does the model generalize across sensors?
  2. Which spoof materials are hardest to detect?
  3. Is performance consistent across LivDet years?
  4. Where does the model fail when sensor x material combinations are split out?

No retraining is required — uses your already-trained best.pth.

Usage (from project root):
    python -m src.evaluation.cross_eval --checkpoint checkpoints/<run>/best.pth
    python -m src.evaluation.cross_eval --checkpoint checkpoints/<run>/best.pth --model resnet50_cbam

Outputs (in results/):
    cross_eval_<tag>_per_sensor.csv
    cross_eval_<tag>_per_material.csv
    cross_eval_<tag>_per_year.csv
    cross_eval_<tag>_sensor_x_material.csv
    cross_eval_<tag>_predictions.csv   # raw (file, y_true, y_prob, …)
    cross_eval_<tag>_report.json       # summary metrics
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config as C
from src.data.dataset import FingerprintDataset, load_manifest
from src.data.transforms import eval_transform
from src.models.factory import get_model, MODEL_REGISTRY
from src.evaluation.metrics import (
    all_metrics, apcer, bpcer, ace, format_metrics,
)


MIN_SAMPLES_PER_SLICE = 20    # don't trust metrics on slices smaller than this


# ─────────────────────────────────────────────────────────────────────────
# Inference
# ─────────────────────────────────────────────────────────────────────────

def run_inference(model, loader, device) -> tuple[np.ndarray, np.ndarray]:
    """Return (y_true, y_prob) for every sample in `loader`."""
    model.eval()
    y_true_all, y_prob_all = [], []
    t0 = time.time()

    with torch.inference_mode():
        for i, (images, labels) in enumerate(loader):
            images = images.to(device, non_blocking=True)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu().numpy().flatten()
            y_prob_all.append(probs)
            y_true_all.append(labels.numpy().astype(int))
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                print(f"  batch {i + 1}/{len(loader)}  ({elapsed:.0f}s)")

    y_true = np.concatenate(y_true_all)
    y_prob = np.concatenate(y_prob_all)
    return y_true, y_prob


# ─────────────────────────────────────────────────────────────────────────
# Slicing helpers
# ─────────────────────────────────────────────────────────────────────────

def slice_metrics(group_df: pd.DataFrame, threshold: float) -> dict:
    """
    Compute metrics for a single slice. Robust to slices that contain
    only one class (live OR spoof). AUC requires both → returned as NaN
    when only one class is present.
    """
    y_true = group_df["y_true"].values
    y_prob = group_df["y_prob"].values
    y_pred = (y_prob >= threshold).astype(int)

    out = {
        "n_total": int(len(group_df)),
        "n_live": int((y_true == 0).sum()),
        "n_spoof": int((y_true == 1).sum()),
        "accuracy": float((y_pred == y_true).mean()),
    }

    both = (y_true == 0).any() and (y_true == 1).any()
    if both:
        m = all_metrics(y_true, y_prob, threshold=threshold)
        out.update({
            "auc": m["roc_auc"],
            "apcer_pct": m["apcer"],
            "bpcer_pct": m["bpcer"],
            "ace_pct": m["ace"],
            "eer_pct": m["eer"],
            "f1": m["f1"],
        })
    else:
        # AUC undefined; report per-class error rate only
        out["auc"] = float("nan")
        out["apcer_pct"] = apcer(y_true, y_pred) if (y_true == 1).any() else float("nan")
        out["bpcer_pct"] = bpcer(y_true, y_pred) if (y_true == 0).any() else float("nan")
        out["ace_pct"] = float("nan")
        out["eer_pct"] = float("nan")
        out["f1"] = float("nan")

    return out


def group_metrics(df: pd.DataFrame, by: list[str],
                  threshold: float) -> pd.DataFrame:
    """Compute metrics for every group of `by`. Skip groups < MIN_SAMPLES_PER_SLICE."""
    rows = []
    for keys, group_df in df.groupby(by, dropna=False):
        if len(group_df) < MIN_SAMPLES_PER_SLICE:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(by, keys))
        row.update(slice_metrics(group_df, threshold))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(by).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────
# Pretty printing
# ─────────────────────────────────────────────────────────────────────────

def print_table(title: str, df: pd.DataFrame, cols: list[str]):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)
    if df.empty:
        print("  (no slices met minimum sample threshold)")
        return
    show = df[cols].copy()
    for c in show.columns:
        if show[c].dtype == float:
            show[c] = show[c].map(lambda v: f"{v:.4f}" if pd.notnull(v) else "—")
    print(show.to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True,
                        help="Path to .pth file (best.pth from a training run).")
    parser.add_argument("--model", type=str, default="resnet50",
                        choices=list(MODEL_REGISTRY.keys()),
                        help="Backbone architecture matching the checkpoint.")
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Classification threshold for APCER/BPCER. "
                             "Use the EER threshold from your test run for fairer comparisons.")
    parser.add_argument("--tag", type=str, default=None,
                        help="Output filename tag. Default: checkpoint folder name.")
    args = parser.parse_args()

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        sys.exit(f"Checkpoint not found: {ckpt_path}")
    tag = args.tag or ckpt_path.parent.name

    device = torch.device(C.device_str())
    print(f"Device: {device}")
    print(f"Checkpoint: {ckpt_path}")
    print(f"Model arch: {args.model}")
    print(f"Threshold:  {args.threshold}")

    # ── Load model ─────────────────────────────────────────────────────
    print("\nLoading model ...")
    model = get_model(args.model, pretrained=False).to(device)
    state = torch.load(ckpt_path, map_location=device, weights_only=False)
    if isinstance(state, dict) and "model_state" in state:
        model.load_state_dict(state["model_state"])
    else:
        model.load_state_dict(state)
    model.eval()

    # ── Build test loader, capture metadata ────────────────────────────
    print("Building test DataLoader ...")
    df_all = load_manifest()
    test_df = df_all[df_all["split"] == "test"].reset_index(drop=True)
    print(f"  test set: {len(test_df):,} images")

    test_loader = DataLoader(
        FingerprintDataset(df_all, "test", eval_transform()),
        batch_size=args.batch,
        shuffle=False,
        num_workers=C.NUM_WORKERS,
        pin_memory=True,
        persistent_workers=C.NUM_WORKERS > 0,
    )

    print("\nRunning inference (one pass over the whole test set) ...")
    t0 = time.time()
    y_true, y_prob = run_inference(model, test_loader, device)
    elapsed = time.time() - t0
    print(f"  done in {elapsed:.0f}s ({len(y_true)/elapsed:.0f} imgs/s)")

    if len(y_true) != len(test_df):
        sys.exit(
            f"Length mismatch: predictions={len(y_true)} vs manifest test={len(test_df)}.\n"
            "DataLoader may have dropped images. Re-run validation: python -m src.data.validate"
        )

    # Attach predictions back to the metadata
    test_df = test_df.copy()
    test_df["y_true"] = y_true
    test_df["y_prob"] = y_prob
    test_df["y_pred"] = (test_df["y_prob"] >= args.threshold).astype(int)
    test_df["correct"] = (test_df["y_pred"] == test_df["y_true"])

    # ── Overall metrics (sanity vs your previous training-script output) ─
    print("\n── Overall test metrics ──")
    overall = all_metrics(y_true, y_prob, threshold=args.threshold)
    print(format_metrics(overall))

    # ── Per-sensor ─────────────────────────────────────────────────────
    per_sensor = group_metrics(test_df, by=["sensor"], threshold=args.threshold)
    print_table(
        "PER-SENSOR PERFORMANCE",
        per_sensor,
        ["sensor", "n_total", "n_live", "n_spoof",
         "auc", "accuracy", "apcer_pct", "bpcer_pct", "ace_pct"],
    )

    # ── Per-year ───────────────────────────────────────────────────────
    per_year = group_metrics(test_df, by=["year"], threshold=args.threshold)
    print_table(
        "PER-YEAR PERFORMANCE",
        per_year,
        ["year", "n_total", "auc", "accuracy",
         "apcer_pct", "bpcer_pct", "ace_pct"],
    )

    # ── Per-material (spoof-only slices give APCER) ────────────────────
    # For 'live' material we report BPCER (per-class error for live).
    per_material = group_metrics(test_df, by=["material"], threshold=args.threshold)
    print_table(
        "PER-MATERIAL PERFORMANCE (live → BPCER, spoof materials → APCER)",
        per_material,
        ["material", "n_total", "n_live", "n_spoof",
         "auc", "accuracy", "apcer_pct", "bpcer_pct"],
    )

    # ── Sensor × Material matrix ───────────────────────────────────────
    sx = group_metrics(test_df, by=["sensor", "material"], threshold=args.threshold)
    print_table(
        "SENSOR × MATERIAL (combined cells)",
        sx,
        ["sensor", "material", "n_total",
         "auc", "accuracy", "apcer_pct", "bpcer_pct", "ace_pct"],
    )

    # ── Save artifacts ─────────────────────────────────────────────────
    out_dir = C.RESULTS_DIR
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    base = out_dir / f"cross_eval_{tag}_{ts}"
    per_sensor.to_csv(f"{base}_per_sensor.csv", index=False)
    per_year.to_csv(f"{base}_per_year.csv", index=False)
    per_material.to_csv(f"{base}_per_material.csv", index=False)
    sx.to_csv(f"{base}_sensor_x_material.csv", index=False)

    # Drop file_path from the prediction dump? Keep it — useful for error analysis.
    pred_cols = ["file_path", "filename", "sensor", "year", "material",
                 "label", "y_true", "y_prob", "y_pred", "correct"]
    test_df[pred_cols].to_csv(f"{base}_predictions.csv", index=False)

    report = {
        "checkpoint": str(ckpt_path),
        "model": args.model,
        "threshold": args.threshold,
        "n_test": int(len(test_df)),
        "overall": {k: v for k, v in overall.items()
                    if k != "confusion_matrix"},
        "confusion_matrix": overall["confusion_matrix"],
        "saved_at": ts,
        "files": {
            "per_sensor": f"{base}_per_sensor.csv",
            "per_year": f"{base}_per_year.csv",
            "per_material": f"{base}_per_material.csv",
            "sensor_x_material": f"{base}_sensor_x_material.csv",
            "predictions": f"{base}_predictions.csv",
        },
    }
    with open(f"{base}_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print()
    print("=" * 78)
    print("FILES WRITTEN")
    print("=" * 78)
    print(f"  {base}_per_sensor.csv")
    print(f"  {base}_per_year.csv")
    print(f"  {base}_per_material.csv")
    print(f"  {base}_sensor_x_material.csv")
    print(f"  {base}_predictions.csv")
    print(f"  {base}_report.json")
    print()
    print("Next steps:")
    print("  • Open the CSVs in Excel — they paste directly into your thesis.")
    print("  • The biggest gap in per_sensor.csv is your generalization story.")
    print("  • Worst row in per_material.csv = your hardest spoof material.")


if __name__ == "__main__":
    main()

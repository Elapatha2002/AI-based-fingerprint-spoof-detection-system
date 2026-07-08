"""
Quantitative XAI faithfulness comparison.

Picks N balanced test images, runs Grad-CAM++ / SHAP / LIME on each,
then computes the faithfulness metrics from src.xai.faithfulness. Writes
a thesis-ready summary table + deletion / insertion curve plots.

Usage:
    python -m src.xai.compare --checkpoint checkpoints/<run>/best.pth
    python -m src.xai.compare --checkpoint <ckpt> --model mobilenetv3_large --n 10

Output (results/xai_compare/<tag>_<ts>/):
    per_image.csv          one row per (image, method): every metric
    summary.csv            mean ± SD per method (thesis Table 4.X)
    summary.json           same content, JSON for programmatic use
    cross_method.csv       pairwise method correlations + IoU
    curves_deletion.png    average deletion curves per method
    curves_insertion.png   average insertion curves per method
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config as C
from src.data.dataset import load_manifest
from src.models.factory import get_model, MODEL_REGISTRY
from src.xai import gradcam, shap_explainer, lime_explainer
from src.xai.base import preprocess, disable_inplace_ops, clear_all_hooks
from src.xai.faithfulness import evaluate_one
from src.xai.gallery import pick_balanced_samples


METHODS = ["gradcam", "shap", "lime"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model", default="resnet50",
                        choices=list(MODEL_REGISTRY.keys()))
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--steps", type=int, default=20,
                        help="Number of deletion/insertion bins.")
    parser.add_argument("--lime-samples", type=int, default=500,
                        help="LIME perturbation samples (lower for speed).")
    parser.add_argument("--shap-bg", type=int, default=16)
    parser.add_argument("--skip", nargs="*", default=[],
                        choices=METHODS)
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        sys.exit(f"Checkpoint not found: {ckpt}")
    tag = args.tag or ckpt.parent.name
    device = torch.device(C.device_str())

    print(f"Device : {device}")
    print(f"Model  : {args.model}")
    print(f"Ckpt   : {ckpt}")
    print(f"N images: {args.n}")
    print(f"Steps  : {args.steps}")

    # ── Load model ─────────────────────────────────────────────────
    print("\nLoading model ...")
    model = get_model(args.model, pretrained=False).to(device)
    state = torch.load(ckpt, map_location=device, weights_only=False)
    if isinstance(state, dict) and "model_state" in state:
        model.load_state_dict(state["model_state"])
    else:
        model.load_state_dict(state)
    model.eval()
    disable_inplace_ops(model)
    clear_all_hooks(model)

    # ── Pick balanced sample ──────────────────────────────────────
    df = load_manifest()
    test_df = df[df["split"] == "test"].reset_index(drop=True)
    samples = pick_balanced_samples(test_df, args.n)
    print(f"\nSelected {len(samples)} samples "
          f"({(samples['label'] == 'live').sum()} live, "
          f"{(samples['label'] == 'spoof').sum()} spoof)")

    # ── Output folder ─────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = C.RESULTS_DIR / "xai_compare" / f"{tag}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output : {out_dir}")

    per_image_rows: list[dict] = []
    cross_rows: list[dict] = []
    del_curves = {m: [] for m in METHODS}     # collected curves per method
    ins_curves = {m: [] for m in METHODS}

    # ── Loop over images ─────────────────────────────────────────
    for i, row in samples.iterrows():
        idx = i + 1
        path = row["file_path"]
        filename = row["filename"]
        true_label = row["label"]

        clear_all_hooks(model)
        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception as e:
            print(f"  [{idx:02d}] skip {filename} (decode error: {e})")
            continue

        print(f"\n[{idx:02d}/{len(samples)}] {filename}  (true={true_label})")

        # Compute the three heatmaps once
        heatmaps: dict[str, np.ndarray] = {}
        timings: dict[str, int] = {}

        if "gradcam" not in args.skip:
            t0 = time.time()
            try:
                r = gradcam.explain(model, img, args.model, device)
                heatmaps["gradcam"] = r.heatmap
                timings["gradcam"] = r.compute_ms
                print(f"     Grad-CAM++  computed in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     Grad-CAM++ FAILED: {e}")

        if "shap" not in args.skip:
            t0 = time.time()
            try:
                r = shap_explainer.explain(model, img, args.model, device,
                                           background_n=args.shap_bg)
                heatmaps["shap"] = r.heatmap
                timings["shap"] = r.compute_ms
                print(f"     SHAP        computed in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     SHAP FAILED: {e}")

        if "lime" not in args.skip:
            t0 = time.time()
            try:
                r = lime_explainer.explain(model, img, args.model, device,
                                            num_samples=args.lime_samples)
                heatmaps["lime"] = r.heatmap
                timings["lime"] = r.compute_ms
                print(f"     LIME        computed in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     LIME FAILED: {e}")

        if not heatmaps:
            print("     (no methods succeeded; skipping faithfulness eval)")
            continue

        # Compute faithfulness metrics
        t0 = time.time()
        img_tensor = preprocess(img)
        report = evaluate_one(model, img_tensor, heatmaps,
                              steps=args.steps, device=device)
        print(f"     Faithfulness done in {time.time()-t0:.1f}s")

        for method, m in report["per_method"].items():
            print(f"       {method:10s}  del-AUC={m['deletion_auc']:.3f}  "
                  f"ins-AUC={m['insertion_auc']:.3f}  "
                  f"sparsity={m['sparsity']:.2f}")
            per_image_rows.append({
                "idx": idx,
                "filename": filename,
                "true_label": true_label,
                "sensor": row.get("sensor"),
                "material": row.get("material"),
                "method": method,
                "deletion_auc": m["deletion_auc"],
                "insertion_auc": m["insertion_auc"],
                "sparsity": m["sparsity"],
                "compute_ms": timings.get(method),
            })
            del_curves[method].append(m["del_curve"])
            ins_curves[method].append(m["ins_curve"])

        for pair, vals in report["cross_method"].items():
            cross_rows.append({
                "idx": idx,
                "filename": filename,
                "pair": pair,
                "pearson": vals["pearson"],
                "spearman": vals["spearman"],
                "iou_top20": vals["iou_top20"],
            })

    if not per_image_rows:
        print("\nNo successful evaluations. Nothing to write.")
        return

    # ── Per-image CSV ─────────────────────────────────────────────
    per_image_df = pd.DataFrame(per_image_rows)
    per_image_df.to_csv(out_dir / "per_image.csv", index=False)

    # ── Summary table (mean ± SD per method) ─────────────────────
    summary_rows = []
    for method in METHODS:
        sub = per_image_df[per_image_df["method"] == method]
        if len(sub) == 0:
            continue
        summary_rows.append({
            "method": method,
            "n_images": len(sub),
            "deletion_auc_mean": float(sub["deletion_auc"].mean()),
            "deletion_auc_sd": float(sub["deletion_auc"].std()),
            "insertion_auc_mean": float(sub["insertion_auc"].mean()),
            "insertion_auc_sd": float(sub["insertion_auc"].std()),
            "sparsity_mean": float(sub["sparsity"].mean()),
            "compute_ms_mean": float(sub["compute_ms"].mean()) if "compute_ms" in sub else None,
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out_dir / "summary.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(summary_rows, indent=2))

    # ── Cross-method CSV ─────────────────────────────────────────
    cross_df = pd.DataFrame(cross_rows)
    cross_df.to_csv(out_dir / "cross_method.csv", index=False)

    cross_summary = []
    for pair in cross_df["pair"].unique():
        sub = cross_df[cross_df["pair"] == pair]
        cross_summary.append({
            "pair": pair,
            "pearson_mean": float(sub["pearson"].mean()),
            "spearman_mean": float(sub["spearman"].mean()),
            "iou_top20_mean": float(sub["iou_top20"].mean()),
        })
    cross_summary_df = pd.DataFrame(cross_summary)
    cross_summary_df.to_csv(out_dir / "cross_method_summary.csv", index=False)

    # ── Curves ────────────────────────────────────────────────────
    _plot_curves(del_curves, "Deletion curves (lower → faster confidence drop)",
                 out_dir / "curves_deletion.png", ylabel="P(target class)")
    _plot_curves(ins_curves, "Insertion curves (higher → faster recovery)",
                 out_dir / "curves_insertion.png", ylabel="P(target class)")

    # ── Final stdout summary ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("FAITHFULNESS SUMMARY  (thesis Table 4.X)")
    print("=" * 70)
    print(summary_df[["method", "deletion_auc_mean", "deletion_auc_sd",
                      "insertion_auc_mean", "insertion_auc_sd",
                      "sparsity_mean", "compute_ms_mean"]]
          .round(3).to_string(index=False))

    print("\n" + "=" * 70)
    print("CROSS-METHOD AGREEMENT  (thesis Table 4.Y)")
    print("=" * 70)
    print(cross_summary_df.round(3).to_string(index=False))

    print(f"\nFiles written to {out_dir}")
    print("\nInterpretation cheat-sheet:")
    print("  Deletion-AUC  lower is better (lose confidence quickly = faithful)")
    print("  Insertion-AUC higher is better (recover with few pixels = faithful)")
    print("  Pearson r     1.0 = perfect agreement between methods")
    print("  IoU top-20%   1.0 = methods agree on the same important regions")


def _plot_curves(curves_by_method: dict[str, list[list[float]]],
                 title: str, out_path: Path, ylabel: str):
    """Plot mean curve per method with ±SD shading."""
    fig, ax = plt.subplots(figsize=(6.5, 4.0), dpi=130)
    colors = {"gradcam": "#58A6FF", "shap": "#F85149", "lime": "#A371F7"}
    labels = {"gradcam": "Grad-CAM++", "shap": "SHAP", "lime": "LIME"}

    for method, curves in curves_by_method.items():
        if not curves:
            continue
        arr = np.array(curves)            # (n_images, n_steps + 1)
        mean = arr.mean(axis=0)
        sd = arr.std(axis=0)
        x = np.linspace(0, 1, len(mean))
        c = colors.get(method, "#808080")
        ax.plot(x, mean, label=labels[method], color=c, linewidth=2)
        ax.fill_between(x, mean - sd, mean + sd, color=c, alpha=0.18)

    ax.set_xlabel("Fraction of pixels modified")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11)
    ax.legend(loc="best", frameon=False)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.set_ylim(-0.02, 1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()

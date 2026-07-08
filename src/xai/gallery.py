"""
Build the XAI gallery — thesis Figure 4 (and survey stimulus material).

Loads a trained checkpoint and runs Grad-CAM++, SHAP, and LIME on a small,
balanced selection of test images. For each image, produces:

  • A 4-panel figure (original + 3 XAI overlays) → PNG
  • A row in a manifest CSV summarizing the predictions and timings

Output lands in:
    results/xai_gallery/<run_tag>_<timestamp>/
        001_<label>_<filename>.png
        002_...
        gallery_manifest.csv

Usage (from project root):

    python -m src.xai.gallery --checkpoint checkpoints/<run>/best.pth
    python -m src.xai.gallery --checkpoint <…> --model mobilenetv3_large --n 12
    python -m src.xai.gallery --checkpoint <…> --skip shap   # fast (Grad+LIME only)

On CPU expect ~20 s/image for all three methods. Plan accordingly.
"""
from __future__ import annotations

import argparse
import csv
import io
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


def pick_balanced_samples(test_df: pd.DataFrame, n: int,
                          seed: int = 42) -> pd.DataFrame:
    """Pick N test rows: half live, half spoof, diverse sensors/materials."""
    rng = np.random.default_rng(seed)
    n_per_class = max(1, n // 2)

    live = test_df[test_df["label"] == "live"].sample(
        n=min(n_per_class, (test_df["label"] == "live").sum()),
        random_state=seed,
    )
    spoof_pool = test_df[test_df["label"] == "spoof"]

    # Try to diversify across materials and sensors
    spoof = []
    materials = list(spoof_pool["material"].dropna().unique())
    rng.shuffle(materials)
    per_material = max(1, n_per_class // max(1, len(materials)))
    for m in materials:
        sub = spoof_pool[spoof_pool["material"] == m]
        spoof.append(sub.sample(min(per_material, len(sub)),
                                random_state=seed))
        if sum(len(x) for x in spoof) >= n_per_class:
            break

    spoof_df = pd.concat(spoof).sample(min(n_per_class,
                                          sum(len(x) for x in spoof)),
                                       random_state=seed)
    return pd.concat([live, spoof_df]).sample(frac=1,
                                              random_state=seed).reset_index(drop=True)


def predict_one(model, pil_image, device) -> tuple[str, float]:
    """Run the model on one image, return (label, P(spoof))."""
    x = preprocess(pil_image).to(device)
    with torch.inference_mode():
        logit = model(x).item()
    p_spoof = 1.0 / (1.0 + np.exp(-logit))
    return ("spoof" if p_spoof >= 0.5 else "live"), float(p_spoof)


def render_panel(orig: Image.Image, results: dict,
                 title: str, out_path: Path) -> None:
    """4-panel figure: original + Grad-CAM++ + SHAP + LIME."""
    methods = ["gradcam", "shap", "lime"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), dpi=140)
    fig.patch.set_facecolor("#0B0F14")

    axes[0].imshow(orig.resize((224, 224)))
    axes[0].set_title("Original", color="white", fontsize=11)
    axes[0].axis("off")

    for ax, m in zip(axes[1:], methods):
        r = results.get(m)
        if r is None:
            ax.text(0.5, 0.5, f"{m}\nskipped",
                    ha="center", va="center",
                    transform=ax.transAxes, color="white")
            ax.axis("off")
            continue
        img = Image.open(io.BytesIO(r.overlay_png))
        ax.imshow(img)
        label = {"gradcam": "Grad-CAM++", "shap": "SHAP", "lime": "LIME"}[m]
        ax.set_title(f"{label}  ·  {r.compute_ms} ms",
                     color="white", fontsize=11)
        ax.axis("off")

    fig.suptitle(title, color="white", fontsize=12, y=0.06)
    fig.tight_layout()
    fig.savefig(out_path, facecolor="#0B0F14", bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True,
                        help="Path to .pth file (best.pth).")
    parser.add_argument("--model", default="resnet50",
                        choices=list(MODEL_REGISTRY.keys()))
    parser.add_argument("--n", type=int, default=10,
                        help="Number of test images to explain.")
    parser.add_argument("--skip", nargs="*", default=[],
                        choices=["gradcam", "shap", "lime"],
                        help="Methods to skip (for fast iteration).")
    parser.add_argument("--lime-samples", type=int, default=800,
                        help="LIME num_samples. Lower = faster, less stable.")
    parser.add_argument("--shap-bg", type=int, default=16,
                        help="SHAP background set size.")
    parser.add_argument("--tag", type=str, default=None,
                        help="Output folder tag. Default: checkpoint folder name.")
    args = parser.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        sys.exit(f"Checkpoint not found: {ckpt}")
    tag = args.tag or ckpt.parent.name
    device = torch.device(C.device_str())

    print(f"Device : {device}")
    print(f"Model  : {args.model}")
    print(f"Ckpt   : {ckpt}")
    print(f"Skip   : {args.skip or '(none)'}")

    # ── Load model ─────────────────────────────────────────────────────
    print("\nLoading model ...")
    model = get_model(args.model, pretrained=False).to(device)
    state = torch.load(ckpt, map_location=device, weights_only=False)
    if isinstance(state, dict) and "model_state" in state:
        model.load_state_dict(state["model_state"])
    else:
        model.load_state_dict(state)
    model.eval()
    disable_inplace_ops(model)             # fix autograd-hook conflicts pre-emptively
    clear_all_hooks(model)

    # ── Pick balanced sample ───────────────────────────────────────────
    df = load_manifest()
    test_df = df[df["split"] == "test"].reset_index(drop=True)
    samples = pick_balanced_samples(test_df, args.n)
    print(f"\nSelected {len(samples)} samples "
          f"({(samples['label'] == 'live').sum()} live, "
          f"{(samples['label'] == 'spoof').sum()} spoof)")

    # ── Output folder ─────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = C.RESULTS_DIR / "xai_gallery" / f"{tag}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out_dir}")

    manifest_rows = []

    # ── Loop ─────────────────────────────────────────────────────────
    for i, row in samples.iterrows():
        idx = i + 1
        path = row["file_path"]
        true_label = row["label"]
        filename = row["filename"]

        clear_all_hooks(model)             # guarantee clean state before each image

        try:
            img = Image.open(path)
            if img.mode != "RGB":
                img = img.convert("RGB")
        except Exception as e:
            print(f"  [{idx:02d}] skip {filename} (decode error: {e})")
            continue

        pred_label, p_spoof = predict_one(model, img, device)
        correct = (pred_label == true_label)
        print(f"\n[{idx:02d}/{len(samples)}] {filename}")
        print(f"     true={true_label}  pred={pred_label}  "
              f"P(spoof)={p_spoof:.3f}  {'✓' if correct else '✗'}")

        results: dict = {}

        if "gradcam" not in args.skip:
            t0 = time.time()
            try:
                results["gradcam"] = gradcam.explain(model, img, args.model, device)
                print(f"     Grad-CAM++  done in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     Grad-CAM++ FAILED: {e}")

        if "shap" not in args.skip:
            t0 = time.time()
            try:
                results["shap"] = shap_explainer.explain(
                    model, img, args.model, device,
                    background_n=args.shap_bg,
                )
                print(f"     SHAP        done in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     SHAP FAILED: {e}")

        if "lime" not in args.skip:
            t0 = time.time()
            try:
                results["lime"] = lime_explainer.explain(
                    model, img, args.model, device,
                    num_samples=args.lime_samples,
                )
                print(f"     LIME        done in {time.time()-t0:.1f}s")
            except Exception as e:
                print(f"     LIME FAILED: {e}")

        # Save panel
        title = (f"{filename}   true={true_label.upper()}   "
                 f"pred={pred_label.upper()}   P(spoof)={p_spoof:.2f}")
        out_path = out_dir / f"{idx:03d}_{true_label}_{Path(filename).stem}.png"
        render_panel(img, results, title, out_path)

        manifest_rows.append({
            "idx": idx,
            "filename": filename,
            "true_label": true_label,
            "pred_label": pred_label,
            "p_spoof": round(p_spoof, 4),
            "correct": correct,
            "sensor": row.get("sensor"),
            "material": row.get("material"),
            "year": row.get("year"),
            "panel_file": out_path.name,
            "gradcam_ms": results.get("gradcam").compute_ms
                          if "gradcam" in results else None,
            "shap_ms": results.get("shap").compute_ms
                       if "shap" in results else None,
            "lime_ms": results.get("lime").compute_ms
                       if "lime" in results else None,
            "gradcam_summary": (results["gradcam"].summary
                                 if "gradcam" in results else None),
            "shap_summary": (results["shap"].summary
                              if "shap" in results else None),
            "lime_summary": (results["lime"].summary
                              if "lime" in results else None),
        })

    # ── Manifest CSV ───────────────────────────────────────────────────
    if manifest_rows:
        manifest_path = out_dir / "gallery_manifest.csv"
        pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
        print(f"\n{'='*60}")
        print("GALLERY COMPLETE")
        print(f"{'='*60}")
        print(f"  Folder:     {out_dir}")
        print(f"  Panels:     {len(manifest_rows)}")
        print(f"  Manifest:   {manifest_path}")
        print("\nThesis next steps:")
        print("  • Pick 3 panels for thesis Figure 4 (1 live, 1 spoof, 1 borderline)")
        print("  • Pick 3 different panels as practitioner-survey stimulus images")


if __name__ == "__main__":
    main()

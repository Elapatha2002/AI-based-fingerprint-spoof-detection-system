"""
Chapter 4 figures — generates PNGs into assets/figures/.

All figures are produced from real result JSONs and cross-eval CSVs. No
synthetic numbers. Run:

    python scripts/figures_ch4.py

Produces:
  assets/figures/ch4_model_comparison.png     — Figure 4.1
  assets/figures/ch4_ablation_v1_v2.png       — Figure 4.2
  assets/figures/ch4_confusion_matrix.png     — Figure 4.3
  assets/figures/ch4_per_sensor.png           — Figure 4.4
  assets/figures/ch4_training_curves.png      — Figure 4.5
  assets/figures/ch4_fsd_cbam_diagram.png     — Figure 4.6
  assets/figures/ch4_system_architecture.png  — Figure 4.7
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
CHECKPOINTS = PROJECT_ROOT / "checkpoints"
FIG_OUT = PROJECT_ROOT / "assets" / "figures"
FIG_OUT.mkdir(parents=True, exist_ok=True)

DPI = 180

# ── Colour palette (colour-blind friendly, print-safe) ───────────────
PALETTE = {
    "resnet50":          "#1f77b4",  # blue
    "resnet50_cbam":     "#ff7f0e",  # orange
    "mobilenetv3_large": "#2ca02c",  # green
    "fsd_cbam_v1":       "#d62728",  # red
    "fsd_cbam_v2":       "#9467bd",  # purple (novel model — highlight)
}
LABELS = {
    "resnet50":          "ResNet50V2",
    "resnet50_cbam":     "ResNet50+CBAM",
    "mobilenetv3_large": "MobileNetV3-L",
    "fsd_cbam_v1":       "FSD-CBAM v1",
    "fsd_cbam_v2":       "FSD-CBAM v2\n(novel)",
}

# ── Test-metrics JSON files ──────────────────────────────────────────
METRICS_FILES = {
    "resnet50":          "resnet50_20260612_102208_test_metrics.json",
    "resnet50_cbam":     "resnet50_cbam_20260612_145118_test_metrics.json",
    "mobilenetv3_large": "mobilenetv3_large_20260616_105902_test_metrics.json",
    "fsd_cbam_v1":       "fsd_cbam_20260708_144619_test_metrics.json",
    "fsd_cbam_v2":       "fsd_cbam_v2_20260810_122231_test_metrics.json",
}

# Cross-eval per-sensor CSVs (v2 not yet generated — use v1 as placeholder)
XEVAL_FILES = {
    "resnet50":          "cross_eval_resnet50_20260612_102208_20260616_101926_per_sensor.csv",
    "resnet50_cbam":     "cross_eval_resnet50_cbam_20260616_201015_per_sensor.csv",
    "mobilenetv3_large": "cross_eval_mobilenetv3_large_20260616_170340_per_sensor.csv",
    "fsd_cbam_v1":       "cross_eval_fsd_cbam_20260709_102251_per_sensor.csv",
}


def load_metrics() -> dict[str, dict]:
    out = {}
    for key, fname in METRICS_FILES.items():
        p = RESULTS / fname
        if p.exists():
            out[key] = json.loads(p.read_text())
    return out


# ─────────────────────────────────────────────────────────────────────
# Figure 4.1 — 5-model test comparison
# ─────────────────────────────────────────────────────────────────────

def fig_model_comparison():
    m = load_metrics()
    keys = ["resnet50", "resnet50_cbam", "mobilenetv3_large",
            "fsd_cbam_v1", "fsd_cbam_v2"]

    metrics = [
        ("AUC (higher is better)", "roc_auc",  1.0,   False),
        ("Accuracy % (higher)",     "accuracy", 100.0, False),
        ("APCER % (lower is better)", "apcer",  1.0,   True),
        ("ACE % (lower is better)",   "ace",    1.0,   True),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=DPI)
    for ax, (title, field, mult, lower_better) in zip(axes.flat, metrics):
        values = [m[k][field] * mult for k in keys]
        colors = [PALETTE[k] for k in keys]
        bars = ax.bar(range(len(keys)), values, color=colors,
                       edgecolor="black", linewidth=0.5)

        # Highlight the winner
        winner_idx = int(np.argmin(values)) if lower_better else int(np.argmax(values))
        bars[winner_idx].set_edgecolor("#000")
        bars[winner_idx].set_linewidth(2.5)

        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([LABELS[k] for k in keys], rotation=25,
                            ha="right", fontsize=8)
        ax.grid(axis="y", linestyle=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Value labels
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() * 1.005,
                     f"{v:.4f}" if v < 2 else f"{v:.2f}",
                     ha="center", va="bottom", fontsize=8)

        # y-limits with breathing room
        vmin, vmax = min(values), max(values)
        if lower_better:
            ax.set_ylim(0, vmax * 1.25)
        else:
            ax.set_ylim(vmin * 0.985, vmax * 1.015)

    fig.suptitle("Figure 4.1  |  Test-set metrics across the five backbones "
                 "(bold outline = best)", fontsize=12, fontweight="bold", y=1.00)
    fig.tight_layout()
    out = FIG_OUT / "ch4_model_comparison.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.2 — FSD-CBAM v1 vs v2 ablation
# ─────────────────────────────────────────────────────────────────────

def fig_ablation():
    m = load_metrics()
    v1, v2 = m["fsd_cbam_v1"], m["fsd_cbam_v2"]

    metrics = [
        ("AUC", "roc_auc", 1.0, False),
        ("Accuracy %", "accuracy", 100.0, False),
        ("APCER %", "apcer", 1.0, True),
        ("BPCER %", "bpcer", 1.0, True),
        ("ACE %", "ace", 1.0, True),
        ("EER %", "eer", 1.0, True),
    ]

    labels = [name for name, *_ in metrics]
    v1_vals = [v1[f] * mult for _, f, mult, _ in metrics]
    v2_vals = [v2[f] * mult for _, f, mult, _ in metrics]

    x = np.arange(len(labels))
    w = 0.36

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=DPI)
    b1 = ax.bar(x - w / 2, v1_vals, w, label="FSD-CBAM v1",
                 color="#d62728", edgecolor="black", linewidth=0.5)
    b2 = ax.bar(x + w / 2, v2_vals, w, label="FSD-CBAM v2 (refined)",
                 color="#9467bd", edgecolor="black", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_title("Figure 4.2  |  FSD-CBAM v1 → v2 ablation "
                  "(three architectural refinements)", fontsize=12,
                  fontweight="bold")
    ax.set_ylabel("Metric value", fontsize=10)
    ax.legend(loc="upper right", frameon=True)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Annotate each bar
    for bar, v in zip(list(b1) + list(b2), v1_vals + v2_vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + max(v1_vals + v2_vals) * 0.01,
                 f"{v:.2f}" if v > 1 else f"{v:.3f}",
                 ha="center", va="bottom", fontsize=8)

    # Percent-change deltas below x-axis
    delta_texts = []
    for name, f, mult, lower_better in metrics:
        d = (v2[f] - v1[f]) * mult
        d_pct = 100 * (v2[f] - v1[f]) / v1[f]
        good = (d < 0) if lower_better else (d > 0)
        marker = "▼" if lower_better else "▲"
        color = "#2ca02c" if good else "#d62728"
        delta_texts.append((f"{marker} {d_pct:+.1f}%", color))

    for i, (txt, color) in enumerate(delta_texts):
        ax.annotate(txt, xy=(i, 0), xytext=(i, -max(v1_vals + v2_vals) * 0.11),
                     ha="center", fontsize=9, color=color, fontweight="bold",
                     annotation_clip=False)

    fig.tight_layout()
    out = FIG_OUT / "ch4_ablation_v1_v2.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.3 — Confusion matrix (FSD-CBAM v2)
# ─────────────────────────────────────────────────────────────────────

def fig_confusion_matrix():
    m = load_metrics()
    cm = np.array(m["fsd_cbam_v2"]["confusion_matrix"])

    labels = ["Spoof (0)", "Live (1)"]

    fig, ax = plt.subplots(figsize=(7, 6), dpi=DPI)
    im = ax.imshow(cm, cmap="Purples")

    # Annotate cells
    total = cm.sum()
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            count = cm[i, j]
            pct = 100 * count / total
            colour = "white" if count > cm.max() / 2 else "black"
            ax.text(j, i, f"{count:,}\n({pct:.2f}%)",
                     ha="center", va="center", color=colour,
                     fontsize=13, fontweight="bold")

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Predicted class", fontsize=11, fontweight="bold")
    ax.set_ylabel("True class", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.3  |  FSD-CBAM v2 confusion matrix "
                  "(test partition, n = 29,840)",
                  fontsize=12, fontweight="bold", pad=15)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Sample count")

    fig.tight_layout()
    out = FIG_OUT / "ch4_confusion_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.4 — Per-sensor ACE across 4 models
# ─────────────────────────────────────────────────────────────────────

def fig_per_sensor():
    dfs = {}
    for key, fname in XEVAL_FILES.items():
        p = RESULTS / fname
        if p.exists():
            dfs[key] = pd.read_csv(p)

    if not dfs:
        print("  [skip] no per-sensor CSVs available")
        return

    # Use the first df's sensor column as the shared axis
    sensors = list(dfs[next(iter(dfs))]["sensor"])
    x = np.arange(len(sensors))
    width = 0.20

    fig, ax = plt.subplots(figsize=(13, 6), dpi=DPI)

    for i, (key, df) in enumerate(dfs.items()):
        df = df.set_index("sensor").reindex(sensors)
        vals = df["ace_pct"].values
        ax.bar(x + (i - 1.5) * width, vals, width,
                label=LABELS[key], color=PALETTE[key],
                edgecolor="black", linewidth=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(sensors, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Average Classification Error (%)", fontsize=10)
    ax.set_title("Figure 4.4  |  Per-sensor ACE across four backbones "
                  "(lower is better; FSD-CBAM v2 cross-sensor evaluation "
                  "in progress at time of interim submission)",
                  fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", frameon=True, fontsize=9, ncol=2)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    out = FIG_OUT / "ch4_per_sensor.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.5 — Training curves for FSD-CBAM v2
# ─────────────────────────────────────────────────────────────────────

def fig_training_curves():
    hist_path = CHECKPOINTS / "fsd_cbam_v2_20260810_122231" / "history.json"
    if not hist_path.exists():
        print("  [skip] no history.json for FSD-CBAM v2")
        return

    hist = json.loads(hist_path.read_text())
    epochs = [h["epoch"] for h in hist]
    train_loss = [h["train"]["loss"] for h in hist]
    val_loss   = [h["val"]["loss"]   for h in hist]
    train_auc  = [h["train"]["roc_auc"] for h in hist]
    val_auc    = [h["val"]["roc_auc"]   for h in hist]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=DPI)

    # Loss
    ax1.plot(epochs, train_loss, "o-", color="#1f77b4",
              label="Train loss", linewidth=2, markersize=5)
    ax1.plot(epochs, val_loss, "s-", color="#d62728",
              label="Validation loss", linewidth=2, markersize=5)
    ax1.set_xlabel("Epoch", fontsize=10)
    ax1.set_ylabel("Loss (binary cross-entropy)", fontsize=10)
    ax1.set_title("Loss over epochs", fontsize=11, fontweight="bold")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.4)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # AUC
    ax2.plot(epochs, train_auc, "o-", color="#1f77b4",
              label="Train AUC", linewidth=2, markersize=5)
    ax2.plot(epochs, val_auc, "s-", color="#2ca02c",
              label="Validation AUC", linewidth=2, markersize=5)
    ax2.set_xlabel("Epoch", fontsize=10)
    ax2.set_ylabel("ROC-AUC", fontsize=10)
    ax2.set_title("AUC over epochs", fontsize=11, fontweight="bold")
    ax2.legend(loc="lower right", fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.4)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle("Figure 4.5  |  FSD-CBAM v2 training dynamics "
                  "(convergence within ~10 epochs)", fontsize=12,
                  fontweight="bold", y=1.02)
    fig.tight_layout()
    out = FIG_OUT / "ch4_training_curves.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.6 — FSD-CBAM module architecture diagram
# ─────────────────────────────────────────────────────────────────────

def _box(ax, x, y, w, h, text, facecolor="#e8eef7", edgecolor="#1f77b4",
         fontsize=9, fontweight="normal"):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.02,rounding_size=0.03",
                         facecolor=facecolor, edgecolor=edgecolor,
                         linewidth=1.4)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, fontweight=fontweight, wrap=True)


def _arrow(ax, x1, y1, x2, y2, color="#333"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->",
                         mutation_scale=15, color=color, linewidth=1.4)
    ax.add_patch(a)


def fig_fsd_cbam_diagram():
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=DPI)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")

    # Input
    _box(ax, 0.1, 2.0, 1.0, 1.0, "Input\nfeature\nmap\n(C × H × W)",
         fontsize=8, facecolor="#f5f5f5", edgecolor="#666")

    # Multi-scale channel attention
    _box(ax, 1.6, 3.0, 2.2, 1.4,
         "Multi-Scale\nChannel Attention",
         fontsize=10, fontweight="bold",
         facecolor="#ede4f4", edgecolor="#9467bd")

    # MLP-1
    _box(ax, 1.6, 1.6, 0.9, 1.0, "MLP\nr = 8", fontsize=8,
         facecolor="#fff", edgecolor="#9467bd")
    _box(ax, 2.7, 1.6, 0.9, 1.0, "MLP\nr = 16", fontsize=8,
         facecolor="#fff", edgecolor="#9467bd")
    _box(ax, 3.8, 1.6, 0.9, 1.0, "MLP\nr = 32\n(REMOVED\nin v2)",
         fontsize=7, facecolor="#fee", edgecolor="#d62728")

    _arrow(ax, 2.7, 1.6, 2.7, 3.0)

    # Sigmoid gate
    _box(ax, 5.1, 3.0, 1.4, 1.4, "Sigmoid\nchannel\ngate",
         fontsize=9, facecolor="#fff8e1", edgecolor="#f39c12")

    _arrow(ax, 3.8, 3.7, 5.1, 3.7)

    # Multiply
    _box(ax, 6.8, 3.0, 0.7, 1.4, "×",
         fontsize=16, fontweight="bold",
         facecolor="#e8f5e9", edgecolor="#2ca02c")

    _arrow(ax, 6.5, 3.7, 6.8, 3.7)
    _arrow(ax, 1.1, 3.7, 1.6, 3.7)
    _arrow(ax, 1.1, 2.5, 1.1, 3.5)

    # Wide spatial attention
    _box(ax, 7.7, 2.4, 2.2, 1.4,
         "Wide Spatial\nAttention\n(7 × 7 conv in v2;\n11 × 11 in v1)",
         fontsize=8, fontweight="bold",
         facecolor="#ede4f4", edgecolor="#9467bd")

    _arrow(ax, 7.5, 3.7, 7.7, 3.1)

    # Output
    _box(ax, 7.7, 0.4, 2.2, 1.0,
         "Gated feature map\n(C × H × W)",
         fontsize=9, facecolor="#f5f5f5", edgecolor="#666")

    _arrow(ax, 8.8, 2.4, 8.8, 1.4)

    ax.text(5.0, 4.8, "Figure 4.6  |  FSD-CBAM module (v2 configuration)",
             ha="center", fontsize=12, fontweight="bold")
    ax.text(5.0, 0.05,
             "Novel design: multi-scale channel gate + focused 7×7 spatial "
             "kernel, inserted only into layer3 and layer4 of ResNet50.",
             ha="center", fontsize=9, style="italic", color="#555")

    fig.tight_layout()
    out = FIG_OUT / "ch4_fsd_cbam_diagram.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 4.7 — System architecture diagram
# ─────────────────────────────────────────────────────────────────────

def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(13, 6), dpi=DPI)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # Row 1 — Client / UI
    _box(ax, 0.3, 5.0, 2.6, 1.4,
         "Streamlit Web UI\n(examiner workstation)",
         fontsize=10, fontweight="bold",
         facecolor="#e3f2fd", edgecolor="#1976d2")

    # Auth
    _box(ax, 3.3, 5.0, 2.0, 1.4,
         "Login /\nAccount session\n(super admin +\nexaminer roles)",
         fontsize=8, facecolor="#fff3e0", edgecolor="#f57c00")

    # CNN service
    _box(ax, 5.8, 5.0, 2.6, 1.4,
         "CNN inference service\n(FSD-CBAM v2\ncheckpoint)",
         fontsize=9, fontweight="bold",
         facecolor="#ede4f4", edgecolor="#9467bd")

    # XAI service
    _box(ax, 8.8, 5.0, 3.8, 1.4,
         "XAI pipeline\nGrad-CAM++  ·  SHAP  ·  LIME\n(per-image overlays)",
         fontsize=9, fontweight="bold",
         facecolor="#fce4ec", edgecolor="#c2185b")

    # Row 2 — Persistence
    _box(ax, 0.3, 2.4, 2.6, 1.4,
         "SQLite\n(cases, analyses,\nusers, audit log)",
         fontsize=9, facecolor="#e8f5e9", edgecolor="#2e7d32")

    _box(ax, 3.3, 2.4, 2.6, 1.4,
         "AWS S3 bucket\n(images, heatmaps,\nPDF reports)",
         fontsize=9, facecolor="#e0f7fa", edgecolor="#00838f")

    _box(ax, 6.2, 2.4, 3.0, 1.4,
         "PDF report generator\n(fpdf2 · Daubert/Frye layout)",
         fontsize=9, facecolor="#fffde7", edgecolor="#c0ca33")

    _box(ax, 9.4, 2.4, 3.2, 1.4,
         "Audit trail\n(dual-write: session +\ndatabase)",
         fontsize=9, facecolor="#efebe9", edgecolor="#6d4c41")

    # Row 3 — Data
    _box(ax, 2.0, 0.2, 9.0, 1.0,
         "LivDet 2009 + 2011 + 2013 + 2015  (65,267 images  ·  9 sensors  ·  12 spoof materials)",
         fontsize=9, fontweight="bold",
         facecolor="#f5f5f5", edgecolor="#666")

    # Arrows
    _arrow(ax, 1.6, 5.0, 1.6, 3.8)     # UI → SQLite
    _arrow(ax, 2.9, 5.7, 3.3, 5.7)     # UI → Auth
    _arrow(ax, 5.3, 5.7, 5.8, 5.7)     # Auth → CNN
    _arrow(ax, 7.1, 5.7, 8.8, 5.7)     # CNN → XAI
    _arrow(ax, 7.1, 5.0, 4.6, 3.8)     # CNN result → S3
    _arrow(ax, 10.7, 5.0, 7.7, 3.8)    # XAI overlays → PDF
    _arrow(ax, 9.2, 3.1, 4.6, 3.1)     # PDF → S3
    _arrow(ax, 6.5, 1.2, 6.5, 2.4)     # LivDet → PDF area (data flow)
    _arrow(ax, 4.6, 2.4, 4.6, 1.2)     # S3 ↕ LivDet

    ax.text(6.5, 6.7,
             "Figure 4.7  |  End-to-end forensic system architecture",
             ha="center", fontsize=12, fontweight="bold")

    fig.tight_layout()
    out = FIG_OUT / "ch4_system_architecture.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────

def fig_external_bpcer():
    """Figure 4.8 — BPCER on LivDet (in-distribution) vs SOCOFing (external)."""
    # Load LivDet BPCER from FSD-CBAM v2 metrics
    m = load_metrics()
    livdet_bpcer = m["fsd_cbam_v2"]["bpcer"]

    # Load SOCOFing report — take the most recent one
    ext_files = sorted(RESULTS.glob("external_socofing_*.json"))
    ext_files = [f for f in ext_files if "smoke" not in f.stem]
    if not ext_files:
        print("  [skip] no external socofing report")
        return
    socofing = json.loads(ext_files[-1].read_text())
    socofing_bpcer = socofing["error_value_pct"]

    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=DPI)
    labels = ["LivDet 2009-2015\n(in-distribution\n14,376 live images)",
              "SOCOFing\n(external — unseen sensor\n6,000 live images)"]
    values = [livdet_bpcer, socofing_bpcer]
    colors = ["#2ca02c", "#d62728"]
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.6)

    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 2,
                 f"{v:.2f}%", ha="center", va="bottom",
                 fontsize=13, fontweight="bold")

    ax.set_ylim(0, max(values) * 1.20)
    ax.set_ylabel("BPCER (%) — bona-fide images misclassified as spoof",
                   fontsize=11)
    ax.set_title("Figure 4.8  |  Cross-sensor domain shift: BPCER on\n"
                  "in-distribution vs external evaluation "
                  "(FSD-CBAM v2)",
                  fontsize=12, fontweight="bold")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Annotation of the delta
    delta = socofing_bpcer - livdet_bpcer
    ax.annotate(f"+{delta:.1f}\npercentage points",
                 xy=(1, socofing_bpcer),
                 xytext=(0.6, socofing_bpcer * 1.1),
                 fontsize=11, fontweight="bold",
                 color="#d62728",
                 arrowprops=dict(arrowstyle="->", color="#d62728", linewidth=1.5))

    fig.tight_layout()
    out = FIG_OUT / "ch4_external_bpcer.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


def fig_external_pspoof_hist():
    """Figure 4.9 — histogram of P(spoof) on SOCOFing to expose the domain
    shift as a distributional pattern, not just a summary number."""
    ext_files = sorted(RESULTS.glob("external_socofing_*.json"))
    ext_files = [f for f in ext_files if "smoke" not in f.stem]
    if not ext_files:
        print("  [skip] no external socofing report for histogram")
        return
    socofing = json.loads(ext_files[-1].read_text())

    # For the histogram we don't have per-image probs in the JSON —
    # instead we use the p05/p50/p95 summary to describe the distribution
    # in a compact swarm-style plot.
    summary = socofing["prob_summary"]

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=DPI)

    # Draw a distribution box (min-max, p05-p95, median line)
    ax.plot([summary["min"], summary["max"]], [1, 1], color="#666",
             linewidth=1.5, alpha=0.6)  # full range
    ax.fill_betweenx([0.85, 1.15], summary["p05"], summary["p95"],
                      color="#d62728", alpha=0.35, label="5-95th percentile of P(spoof)")
    ax.plot([summary["median"], summary["median"]], [0.75, 1.25],
             color="#d62728", linewidth=3.5, label=f"Median = {summary['median']:.3f}")
    ax.plot([summary["mean"], summary["mean"]], [0.85, 1.15],
             color="black", linewidth=2, linestyle="--",
             label=f"Mean = {summary['mean']:.3f}")

    # Decision threshold at 0.5
    ax.axvline(0.5, color="#333", linestyle=":", linewidth=1.5,
                label="Decision threshold = 0.5")

    ax.set_xlim(0, 1.02)
    ax.set_ylim(0.4, 1.6)
    ax.set_xlabel("Predicted P(spoof) for images that are actually LIVE",
                   fontsize=11)
    ax.set_yticks([])
    ax.set_title("Figure 4.9  |  Distribution of FSD-CBAM v2 P(spoof) on "
                  "the SOCOFing bona-fide dataset\n"
                  "(all 6,000 images are real fingerprints — model is "
                  "confidently, systematically wrong)",
                  fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, frameon=True)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # Zone shading
    ax.axvspan(0, 0.5, alpha=0.08, color="#2ca02c")   # correct region
    ax.axvspan(0.5, 1.0, alpha=0.08, color="#d62728")  # wrong region
    ax.text(0.25, 1.5, "Correct region\n(P(spoof) < 0.5)", ha="center",
             color="#2ca02c", fontsize=9, style="italic")
    ax.text(0.75, 1.5, "Wrong region\n(P(spoof) ≥ 0.5)", ha="center",
             color="#d62728", fontsize=9, style="italic")

    fig.tight_layout()
    out = FIG_OUT / "ch4_external_pspoof_hist.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


def main():
    print("Generating Chapter 4 figures ...")
    fig_model_comparison()
    fig_ablation()
    fig_confusion_matrix()
    fig_per_sensor()
    fig_training_curves()
    fig_fsd_cbam_diagram()
    fig_system_architecture()
    fig_external_bpcer()
    fig_external_pspoof_hist()
    print("Done.")


if __name__ == "__main__":
    main()

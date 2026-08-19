"""
Chapter 5 (Discussion) synthesis figures — three interpretive charts that
organise the raw findings from Chapter 4 into a discussion-ready form.

  assets/figures/ch5_pareto.png            — Figure 5.1: model efficiency Pareto
  assets/figures/ch5_deployment_envelope.png — Figure 5.2: deployment envelope
  assets/figures/ch5_rq_alignment.png      — Figure 5.3: RQ-to-findings alignment

Run:
    python scripts/figures_ch5.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
FIG_OUT = PROJECT_ROOT / "assets" / "figures"
FIG_OUT.mkdir(parents=True, exist_ok=True)

DPI = 180

MODELS = [
    # (short_name, params_millions, ace_pct, colour, is_pareto)
    ("ResNet50V2",       23.5, 5.06, "#1f77b4", False),
    ("ResNet50+CBAM",    26.0, 6.61, "#ff7f0e", False),
    ("MobileNetV3-L",     4.2, 4.60, "#2ca02c", True),
    ("FSD-CBAM v1",      31.8, 6.35, "#d62728", False),
    ("FSD-CBAM v2\n(novel)", 28.5, 4.60, "#9467bd", True),
]


# ─────────────────────────────────────────────────────────────────────
# Figure 5.1 — Model efficiency Pareto (params vs ACE)
# ─────────────────────────────────────────────────────────────────────

def fig_pareto():
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=DPI)

    for name, params, ace, colour, is_pareto in MODELS:
        size = 380 if is_pareto else 200
        edge = "black" if is_pareto else "grey"
        lw = 2.5 if is_pareto else 1.0
        ax.scatter(params, ace, s=size, color=colour, edgecolors=edge,
                    linewidths=lw, zorder=3, alpha=0.9)

        # Label above / below to prevent overlap
        offset_y = -0.7 if name.startswith("MobileNet") else 0.35
        ha = "center"
        ax.annotate(name, xy=(params, ace), xytext=(params, ace + offset_y),
                     ha=ha, fontsize=10, fontweight="bold" if is_pareto else "normal",
                     zorder=4)

    # Pareto frontier — connect the two Pareto-optimal points
    pareto = [(p, a) for _, p, a, _, is_p in MODELS if is_p]
    pareto.sort()
    xs, ys = zip(*pareto)
    ax.plot(xs, ys, "--", color="#666", linewidth=1.5, alpha=0.7,
             label="Pareto frontier", zorder=2)

    # Shading — "efficient region" (bottom-left = ideal)
    xlim = (2, 40)
    ylim = (4.0, 7.5)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    # Ideal-region annotation
    ax.annotate("← Better\n(fewer params,\nlower error)",
                 xy=(4, 4.2), xytext=(4, 4.2),
                 fontsize=10, color="#2ca02c", fontstyle="italic",
                 fontweight="bold", ha="left")

    ax.set_xlabel("Parameter count (millions)  —  proxy for compute cost",
                   fontsize=11)
    ax.set_ylabel("Average Classification Error (%)  —  lower is better",
                   fontsize=11)
    ax.set_title("Figure 5.1  |  Model efficiency Pareto frontier\n"
                  "(MobileNetV3-Large and FSD-CBAM v2 dominate; "
                  "novel model wins on APCER despite larger size)",
                  fontsize=12, fontweight="bold", pad=15)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", fontsize=10, frameon=True)

    fig.tight_layout()
    out = FIG_OUT / "ch5_pareto.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 5.2 — Deployment envelope (2x2 quadrant)
# ─────────────────────────────────────────────────────────────────────

def fig_deployment_envelope():
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=DPI)

    # 2x2 grid: rows = ground-truth class, cols = distribution
    cells = [
        # (row_label, col_label, metric_label, metric_value, colour, verdict)
        ("Real fingerprints", "In-distribution\n(LivDet)",
         "BPCER", "3.32%", "#8fce8f", "READY"),
        ("Real fingerprints", "Out-of-distribution\n(SOCOFing)",
         "BPCER", "73.33%", "#f28b82", "NOT READY"),
        ("Spoof attempts", "In-distribution\n(LivDet)",
         "APCER", "5.87%", "#8fce8f", "READY"),
        ("Spoof attempts", "Out-of-distribution\n(SOCOFing)",
         "APCER", "N/A", "#d3d3d3", "UNTESTED\n(no spoofs\nin SOCOFing)"),
    ]

    for i, (row, col, metric, value, colour, verdict) in enumerate(cells):
        r, c = i // 2, i % 2
        x, y = c, 1 - r
        rect = Rectangle((x, y), 1, 1, facecolor=colour, edgecolor="black",
                          linewidth=1.5, alpha=0.9)
        ax.add_patch(rect)
        ax.text(x + 0.5, y + 0.72, verdict, ha="center", va="center",
                 fontsize=13, fontweight="bold",
                 color="#1a4d1a" if colour == "#8fce8f"
                        else "#7a1a1a" if colour == "#f28b82"
                        else "#555")
        ax.text(x + 0.5, y + 0.45, f"{metric} = {value}",
                 ha="center", va="center", fontsize=13,
                 color="#333")
        ax.text(x + 0.5, y + 0.22,
                 "Model detects spoofs\nreliably" if metric == "APCER" and value != "N/A"
                 else "Model accepts real\nfingerprints correctly" if metric == "BPCER" and value == "3.32%"
                 else "Model rejects real\nfingerprints as spoofs" if metric == "BPCER" and value == "73.33%"
                 else "Cannot evaluate\n(dataset is bona-fide only)",
                 ha="center", va="center", fontsize=10, style="italic",
                 color="#333")

    # Row / column labels
    ax.text(-0.15, 1.5, "Real\nfingerprints\n(bona-fide)", ha="right", va="center",
             fontsize=11, fontweight="bold")
    ax.text(-0.15, 0.5, "Spoof\nattempts", ha="right", va="center",
             fontsize=11, fontweight="bold")
    ax.text(0.5, 2.08, "In-distribution\n(LivDet 2009-2015 sensors)",
             ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.text(1.5, 2.08, "Out-of-distribution\n(unseen sensor, e.g. SecuGen)",
             ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_xlim(-0.5, 2.05)
    ax.set_ylim(-0.1, 2.35)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.text(0.75, -0.05,
             "Figure 5.2  |  Deployment envelope of FSD-CBAM v2  —  "
             "the model is production-ready only on sensor hardware seen\n"
             "during training (green cells); performance collapses on unseen sensors (red).",
             ha="center", va="top", fontsize=11, fontweight="bold",
             transform=ax.transData)

    fig.tight_layout()
    out = FIG_OUT / "ch5_deployment_envelope.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 5.3 — Research-question / findings alignment matrix
# ─────────────────────────────────────────────────────────────────────

def fig_rq_alignment():
    rqs = [
        ("RQ1", "Which backbone offers the best\naccuracy / efficiency / XAI\ntrade-off?",
         [("Ch 4.6 five-model comparison",       "answered"),
          ("Ch 4.7 v1→v2 ablation",              "answered"),
          ("Ch 5.3 Pareto interpretation",       "answered")]),

        ("RQ2", "How consistent and faithful are\nGrad-CAM++, SHAP, and LIME on\nthe same PAD model?",
         [("Ch 4.9 faithfulness (2 of 3 models)", "partial"),
          ("FSD-CBAM v2 faithfulness",            "pending"),
          ("Ch 5.6 cross-method reflection",      "answered")]),

        ("RQ3", "How to construct a forensic\nworkflow admissible under\nDaubert / Frye?",
         [("Ch 4.10 Streamlit + audit + PDF",    "answered"),
          ("Ch 5.7 Daubert / Frye discussion",   "answered"),
          ("Ch 4.11 external-validation disclosure", "answered")]),

        ("RQ4", "How do practitioners perceive\nthe XAI-augmented PAD system?",
         [("Ch 1 / Ch 3.4.1 public perception (n=86)", "answered"),
          ("Ch 5.8 public survey reflection",   "answered"),
          ("Practitioner survey (Oct 2026)",    "pending")]),
    ]

    status_colour = {"answered": "#8fce8f",
                     "partial":  "#ffe082",
                     "pending":  "#f28b82"}

    fig, ax = plt.subplots(figsize=(13, 8), dpi=DPI)

    row_h = 1.0
    ncols = 3
    col_w = 3.0
    x_rq   = 0
    x_desc = 2.2
    x_evid = 5.5

    for i, (rq_id, rq_text, evidence) in enumerate(rqs):
        y = len(rqs) - 1 - i

        # RQ id + description
        ax.text(x_rq + 0.3, y + 0.5, rq_id, fontsize=16, fontweight="bold",
                 va="center", color="#333")
        ax.text(x_desc, y + 0.5, rq_text, fontsize=10, va="center",
                 color="#333")

        # Evidence cells
        for j, (evid_text, status) in enumerate(evidence):
            ex = x_evid + j * col_w
            rect = FancyBboxPatch((ex, y + 0.1), col_w * 0.9, 0.8,
                                    boxstyle="round,pad=0.03,rounding_size=0.05",
                                    facecolor=status_colour[status],
                                    edgecolor="black", linewidth=0.8)
            ax.add_patch(rect)
            ax.text(ex + col_w * 0.45, y + 0.62, evid_text,
                     fontsize=9, ha="center", va="center", color="#111")
            ax.text(ex + col_w * 0.45, y + 0.25, status.upper(),
                     fontsize=9, fontweight="bold", ha="center", va="center",
                     color="#1a4d1a" if status == "answered"
                            else "#8a6d1a" if status == "partial"
                            else "#7a1a1a")

    ax.set_xlim(-0.2, x_evid + ncols * col_w + 0.2)
    ax.set_ylim(-0.5, len(rqs) + 0.4)
    ax.axis("off")

    # Legend
    for k, (label, colour) in enumerate([("Answered", "#8fce8f"),
                                          ("Partial",  "#ffe082"),
                                          ("Pending",  "#f28b82")]):
        rect = Rectangle((k * 2.5, -0.35), 0.4, 0.25,
                          facecolor=colour, edgecolor="black")
        ax.add_patch(rect)
        ax.text(k * 2.5 + 0.5, -0.22, label, fontsize=10, va="center")

    ax.set_title("Figure 5.3  |  Research-question / findings alignment matrix",
                  fontsize=13, fontweight="bold", pad=15)

    fig.tight_layout()
    out = FIG_OUT / "ch5_rq_alignment.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.name}")


# ─────────────────────────────────────────────────────────────────────

def main():
    print("Generating Chapter 5 figures ...")
    fig_pareto()
    fig_deployment_envelope()
    fig_rq_alignment()
    print("Done.")


if __name__ == "__main__":
    main()

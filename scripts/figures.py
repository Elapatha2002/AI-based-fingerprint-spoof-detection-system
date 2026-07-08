"""Generate thesis figures for the Explainable Fingerprint Spoof Detection project.

Produces four PNG figures saved under assets/figures/ at 200 DPI:
    1. rich_picture.png       — End-to-end system rich picture (Chapter 1.8)
    2. conceptual_map.png     — Literature conceptual map (Chapter 2.2)
    3. dsrm_workflow.png      — DSRM six-stage workflow (Chapter 3.5)
    4. project_timeline.png   — Gantt-style project timeline (Chapter 3.7)

Author: K. M. Pasindu Chanuka Elapatha
"""
from pathlib import Path
from datetime import date

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "figures"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Global style — neutral palette, sans-serif, suitable for printed thesis.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "savefig.facecolor": "white",
    "figure.facecolor": "white",
})

NEUTRAL_FILL = "#EAF1F8"
NEUTRAL_EDGE = "#2C3E50"
ACCENT_FILL = "#FCE8D5"
ACCENT_EDGE = "#8B5A2B"
SIDE_FILL = "#E8F1E8"
SIDE_EDGE = "#3D6B3D"
ARROW_COLOR = "#2C3E50"


def _rounded_box(ax, x, y, w, h, text, fill=NEUTRAL_FILL, edge=NEUTRAL_EDGE,
                 fontsize=9, fontweight="normal"):
    """Draw a rounded rectangle with centred text and return its bounding box."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.2, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight=fontweight, color="#1A1A1A", wrap=True)
    return (x, y, w, h)


def _arrow(ax, x1, y1, x2, y2, color=ARROW_COLOR, style="->", lw=1.4):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=14,
        color=color, linewidth=lw,
    ))


# ---------------------------------------------------------------------------
# Figure 1 — Rich Picture
# ---------------------------------------------------------------------------
def make_rich_picture():
    """Rich Picture: 2 rows (top: workflow chain, bottom: side outputs).

    Avoids the previous overflow problem by stacking the chain on a single
    row with larger gaps and concise labels, and placing the two side
    artefacts on their own row below.
    """
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 28)
    ax.set_ylim(0, 14)
    ax.axis("off")

    ax.text(14, 13.2, "Rich Picture: Explainable Fingerprint Spoof Detection System",
            ha="center", va="center", fontsize=14, fontweight="bold")

    # Top row — six-stage horizontal chain.
    y = 8.0
    h = 2.6
    w = 3.8
    gap = 0.6
    n = 6

    stages = [
        ("Fingerprint\nImage\n(BMP / PNG)",                       NEUTRAL_FILL, NEUTRAL_EDGE, "normal"),
        ("Preprocessing\nResize 224x224\nCLAHE + Norm",           NEUTRAL_FILL, NEUTRAL_EDGE, "normal"),
        ("CNN Backbone\nMobileNetV3 /\nResNet50 / CBAM",          ACCENT_FILL,  ACCENT_EDGE,  "bold"),
        ("Verdict +\nConfidence\nEER Gauge",                      ACCENT_FILL,  ACCENT_EDGE,  "bold"),
        ("XAI Panels\nGrad-CAM++\nSHAP / LIME",                   NEUTRAL_FILL, NEUTRAL_EDGE, "normal"),
        ("Forensic PDF\nReport\n(Daubert/Frye)",                  ACCENT_FILL,  ACCENT_EDGE,  "bold"),
    ]

    total_w = n * w + (n - 1) * gap
    x0 = (28 - total_w) / 2

    xs = []
    for i, (label, fill, edge, weight) in enumerate(stages):
        x = x0 + i * (w + gap)
        _rounded_box(ax, x, y, w, h, label, fill=fill, edge=edge,
                     fontsize=9.5, fontweight=weight)
        xs.append(x)

    # Forward arrows between adjacent boxes (only across the small gap).
    for i in range(n - 1):
        x1 = xs[i] + w
        x2 = xs[i + 1]
        _arrow(ax, x1, y + h / 2, x2, y + h / 2)

    # Bottom row — two side artefacts produced from the Verdict stage.
    verdict_x = xs[3] + w / 2
    side_w = 5.5
    side_h = 1.8
    side_y = 3.0
    case_x = verdict_x - side_w - 0.8
    audit_x = verdict_x + 0.8

    _rounded_box(ax, case_x, side_y, side_w, side_h,
                 "Case Management Strip\n(case ID, examiner, exhibit)",
                 fill=SIDE_FILL, edge=SIDE_EDGE, fontsize=9.5)
    _rounded_box(ax, audit_x, side_y, side_w, side_h,
                 "Audit Trail Log\n(timestamp, user, model, hash)",
                 fill=SIDE_FILL, edge=SIDE_EDGE, fontsize=9.5)

    # Connect Verdict box to both side artefacts with branching arrows.
    _arrow(ax, verdict_x, y, case_x + side_w * 0.75, side_y + side_h)
    _arrow(ax, verdict_x, y, audit_x + side_w * 0.25, side_y + side_h)

    # Footer note.
    ax.text(14, 1.0,
            "End-to-end forensic pipeline: image acquisition through explainable verdict to court-admissible report.",
            ha="center", va="center", fontsize=9, style="italic", color="#555555")

    out = ASSETS_DIR / "rich_picture.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", transparent=False)
    plt.close(fig)
    print(f"Wrote: {out}")


# ---------------------------------------------------------------------------
# Figure 2 — Conceptual Map of the Literature
# ---------------------------------------------------------------------------
def make_conceptual_map():
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis("off")

    ax.text(5, 13.5, "Conceptual Map of the Literature",
            ha="center", va="center", fontsize=14, fontweight="bold")

    # Central node.
    _rounded_box(ax, 2.5, 11.4, 5.0, 1.2,
                 "Explainable Fingerprint\nSpoof Detection (PAD)",
                 fill=ACCENT_FILL, edge=ACCENT_EDGE, fontsize=10.5, fontweight="bold")

    # Three branch headers.
    branches = [
        (0.2, 9.6, 3.0, "Domain\nFoundations", NEUTRAL_FILL, NEUTRAL_EDGE),
        (3.5, 9.6, 3.0, "Existing\nPAD Systems", NEUTRAL_FILL, NEUTRAL_EDGE),
        (6.8, 9.6, 3.0, "Technological\nFoundations", NEUTRAL_FILL, NEUTRAL_EDGE),
    ]
    branch_centres = []
    for x, y, w, label, fill, edge in branches:
        _rounded_box(ax, x, y, w, 1.1, label, fill=fill, edge=edge,
                     fontsize=10, fontweight="bold")
        cx = x + w / 2
        branch_centres.append(cx)
        # Connect to central node.
        ax.plot([5, cx], [11.4, y + 1.1], color=ARROW_COLOR, linewidth=1.0)

    # Leaf nodes per branch.
    domain_leaves = [
        "Fingerprint Biometrics",
        "Presentation Attacks",
        "LivDet Benchmark",
        "Forensic Admissibility\n(Daubert / Frye)",
    ]
    pad_leaves = [
        "CNN-based PAD\n[Cheniti, Mukul, Uliyan]",
        "Slim-ResCNN\n[Zhang 2019]",
        "Attention PAD\n[Kothadiya 2023]",
        "Dual-model VGG+ResNet\n[Cheniti 2025]",
        "GAN-hybrid\n[Naeem 2025]",
        "Cross-sensor\n[Reza & Jung]",
        "Texture + Pores\n[Agarwal]",
    ]
    tech_leaves = [
        "CNN Architectures\n(ResNet, MobileNetV3)",
        "Attention\n(CBAM, SE blocks)",
        "XAI Methods\n(Grad-CAM++, SHAP, LIME)",
        "Faithfulness Metrics\n(Deletion / Insertion-AUC)",
        "DSRM\n[Peffers 2007]",
    ]

    def _draw_leaves(cx, leaves, top_y, leaf_w=2.9, leaf_h=0.8, spacing=0.25):
        y = top_y
        for text in leaves:
            x = cx - leaf_w / 2
            _rounded_box(ax, x, y - leaf_h, leaf_w, leaf_h, text,
                         fill="#F7F7F2", edge="#666666", fontsize=8)
            ax.plot([cx, cx], [top_y + 0.25, y - leaf_h / 2], color="#888888",
                    linewidth=0.7, linestyle=":")
            y -= leaf_h + spacing

    _draw_leaves(branch_centres[0], domain_leaves, top_y=9.3)
    _draw_leaves(branch_centres[1], pad_leaves, top_y=9.3)
    _draw_leaves(branch_centres[2], tech_leaves, top_y=9.3)

    ax.text(5, 0.3,
            "Synthesis of domain knowledge, prior PAD work, "
            "and enabling technologies underpinning this study.",
            ha="center", va="center", fontsize=8.5, style="italic", color="#555555")

    out = ASSETS_DIR / "conceptual_map.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", transparent=False)
    plt.close(fig)
    print(f"Wrote: {out}")


# ---------------------------------------------------------------------------
# Figure 3 — DSRM Six-Stage Workflow
# ---------------------------------------------------------------------------
def make_dsrm_workflow():
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.text(10, 9.3,
            "Design Science Research Methodology Workflow (Peffers et al., 2007)",
            ha="center", va="center", fontsize=13, fontweight="bold")

    stages = [
        "Stage 1\nProblem\nIdentification",
        "Stage 2\nDefine\nObjectives",
        "Stage 3\nDesign &\nDevelopment",
        "Stage 4\nDemonstration",
        "Stage 5\nEvaluation",
        "Stage 6\nCommunication",
    ]

    n = len(stages)
    w = 2.6
    h = 2.0
    y = 4.5
    total_w = n * w + (n - 1) * 0.6
    x0 = (20 - total_w) / 2

    centres = []
    for i, label in enumerate(stages):
        x = x0 + i * (w + 0.6)
        fill = ACCENT_FILL if i in (2, 4) else NEUTRAL_FILL
        edge = ACCENT_EDGE if i in (2, 4) else NEUTRAL_EDGE
        _rounded_box(ax, x, y, w, h, label, fill=fill, edge=edge,
                     fontsize=9.5, fontweight="bold")
        centres.append((x + w / 2, y))

    # Forward arrows.
    for i in range(n - 1):
        x1 = centres[i][0] + w / 2
        x2 = centres[i + 1][0] - w / 2
        _arrow(ax, x1, y + h / 2, x2, y + h / 2)

    # Feedback arrow from Stage 5 (index 4) back to Stage 3 (index 2),
    # routed BELOW the boxes so it doesn't cross Stage 4.
    s5_x = centres[4][0]
    s3_x = centres[2][0]
    feedback = FancyArrowPatch(
        (s5_x, y),                 # leave from bottom of Stage 5
        (s3_x, y),                 # arrive at bottom of Stage 3
        connectionstyle="arc3,rad=-0.55",   # negative = curve below
        arrowstyle="->", mutation_scale=16,
        color="#B0413E", linewidth=1.5, linestyle="--",
    )
    ax.add_patch(feedback)
    ax.text((s5_x + s3_x) / 2, y - 2.4,
            "Feedback: refine design after evaluation",
            ha="center", va="center", fontsize=9, color="#B0413E", style="italic")

    ax.text(10, 1.0,
            "Iterative process guiding artefact construction and rigorous evaluation.",
            ha="center", va="center", fontsize=9, style="italic", color="#555555")

    out = ASSETS_DIR / "dsrm_workflow.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", transparent=False)
    plt.close(fig)
    print(f"Wrote: {out}")


# ---------------------------------------------------------------------------
# Figure 4 — Project Timeline (Gantt)
# ---------------------------------------------------------------------------
def make_project_timeline():
    fig, ax = plt.subplots(figsize=(12, 7))

    # (Task, start, end, category)
    tasks = [
        ("Literature Review & Proposal",          date(2026, 4, 1),  date(2026, 5, 31), "Planning"),
        ("Dataset Normalisation",                 date(2026, 5, 1),  date(2026, 5, 31), "Development"),
        ("Preprocessing Pipeline",                date(2026, 5, 10), date(2026, 5, 31), "Development"),
        ("Model Training\n(ResNet50, CBAM, MobileNetV3)",
                                                  date(2026, 6, 1),  date(2026, 7, 20), "Development"),
        ("Cross-Evaluation",                      date(2026, 7, 1),  date(2026, 7, 31), "Evaluation"),
        ("XAI Implementation + Faithfulness",     date(2026, 7, 15), date(2026, 8, 31), "Development"),
        ("Streamlit Application",                 date(2026, 7, 15), date(2026, 8, 31), "Development"),
        ("Practitioner Survey Window",            date(2026, 8, 1),  date(2026, 8, 31), "Evaluation"),
        ("Survey Analysis",                       date(2026, 9, 1),  date(2026, 9, 30), "Evaluation"),
        ("Thesis Writing (Chapters 4-6)",         date(2026, 9, 1),  date(2026, 10, 31), "Writing"),
        ("Final Review + Viva Prep",              date(2026, 10, 15),date(2026, 11, 30), "Writing"),
    ]

    category_colors = {
        "Planning":    "#6FA8DC",
        "Development": "#F6B26B",
        "Evaluation":  "#93C47D",
        "Writing":     "#B895C8",
    }

    y_positions = np.arange(len(tasks))[::-1]
    for i, (name, start, end, cat) in enumerate(tasks):
        s = mdates.date2num(start)
        e = mdates.date2num(end)
        width = e - s
        ax.barh(y_positions[i], width, left=s, height=0.6,
                color=category_colors[cat], edgecolor="#333333", linewidth=0.8)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([t[0] for t in tasks], fontsize=9)

    ax.set_xlim(mdates.date2num(date(2026, 3, 25)),
                mdates.date2num(date(2026, 12, 5)))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.tick_params(axis="x", labelsize=9)

    ax.grid(axis="x", linestyle=":", color="#BBBBBB", linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.set_title("Project Timeline — April to November 2026",
                 fontsize=13, fontweight="bold", pad=14)

    # Legend.
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="#333333")
               for c in category_colors.values()]
    ax.legend(handles, list(category_colors.keys()),
              loc="lower right", frameon=True, fontsize=9, title="Phase Category")

    fig.tight_layout()
    out = ASSETS_DIR / "project_timeline.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", transparent=False)
    plt.close(fig)
    print(f"Wrote: {out}")


def main():
    make_rich_picture()
    make_conceptual_map()
    make_dsrm_workflow()
    make_project_timeline()


if __name__ == "__main__":
    main()

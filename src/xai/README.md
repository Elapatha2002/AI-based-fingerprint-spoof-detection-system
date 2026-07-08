# Phase 5 — Explainable AI

Three XAI methods + a gallery generator. Directly answers Research
Question 2: *"Which XAI technique most effectively highlights forensically
relevant features?"*

## Files

| File | Purpose |
|---|---|
| `base.py` | Shared helpers: target-layer resolver, image preprocessing, overlay rendering, timing |
| `gradcam.py` | Grad-CAM++ wrapper via `pytorch-grad-cam` |
| `shap_explainer.py` | SHAP DeepExplainer wrapper (binary head → 2-class wrapper inside) |
| `lime_explainer.py` | LIME image wrapper |
| `gallery.py` | CLI that produces thesis Figure 4 + survey stimulus images |

All three methods return the same `XAIResult` dataclass — making it trivial
to swap into the Streamlit app's `explain()` interface.

## Install the XAI libraries

From the project root, **inside your venv**:

```cmd
pip install -r src\requirements.txt
```

New libraries pulled in for Phase 5:
- `grad-cam` (the pytorch-grad-cam package)
- `shap` (Shapley value attribution)
- `lime` (Local Interpretable Model-agnostic Explanations)
- `scikit-image` (for LIME's superpixel segmentation)
- `matplotlib` (overlay rendering)

## Step 1 — Sanity check (1 image, ~30 s on CPU)

```cmd
cd "D:\Projects\University\Final year Resarch project"
python -m src.xai.gallery --checkpoint checkpoints\resnet50_20260612_102208\best.pth --n 1
```

You'll get one 4-panel PNG in `results/xai_gallery/<run>_<ts>/`. Open
it — three heatmaps should appear next to the original.

## Step 2 — Full thesis gallery (10 images, ~3 min on CPU)

```cmd
python -m src.xai.gallery --checkpoint checkpoints\resnet50_20260612_102208\best.pth --n 10
```

Produces:
- 10 PNG panels in `results/xai_gallery/<run>_<ts>/`
- `gallery_manifest.csv` with predictions, timings, and per-method summaries

For the survey stimulus images, run the same command on your best model
(probably MobileNetV3-Large) so the survey shows the deployment-tier outputs.

## Step 3 — Compare methods quantitatively

Open `gallery_manifest.csv` in Excel. The `*_ms` columns give wall-clock
time per method per image — perfect data for the speed comparison in your
Chapter 4 XAI section.

## Flags

| Flag | Default | When to use |
|---|---|---|
| `--n 10` | 10 | Number of test images to explain |
| `--model resnet50_cbam` | `resnet50` | Match the checkpoint's architecture |
| `--skip shap lime` | — | Iterate quickly with Grad-CAM only |
| `--lime-samples 800` | 800 | Lower for speed, higher for stability |
| `--shap-bg 16` | 16 | Background distribution size for SHAP |
| `--tag mygallery` | checkpoint folder name | Custom output folder name |

## Timings on CPU (per image)

| Method | Time | Notes |
|---|---|---|
| Grad-CAM++ | ~1–3 s | Fast — uses a single backward pass |
| SHAP DeepExplainer | ~3–10 s | Scales with `--shap-bg` |
| LIME | ~10–25 s | Scales with `--lime-samples` |

10-image gallery on CPU: budget 4–8 minutes total.

## How each method differs (one paragraph each — for thesis)

**Grad-CAM++** is a **gradient-based** method. It backpropagates the
class score gradient back to the last conv layer, then weights each
channel by its average gradient. Fast and sensitive to where the model
attends, but the heatmap is coarse (limited to the conv layer's spatial
resolution, typically 7×7 upsampled to 224×224).

**SHAP DeepExplainer** is an **attribution** method based on Shapley
values from cooperative game theory. It estimates how each input
feature (pixel / channel) contributes — *positively or negatively* — to
the prediction, against a background distribution of "reference" images.
Slower than Grad-CAM++ but mathematically more principled and supports
*signed* attributions (red = pushes toward spoof, blue = pushes toward live).

**LIME** is a **model-agnostic** method. It segments the image into
superpixels, perturbs them, and fits a sparse linear surrogate to
approximate the model's behavior locally. Outputs the most influential
superpixels as a piecewise-constant mask. The slowest method but the
easiest to interpret for non-technical viewers — exactly the audience
your forensic-admissibility narrative targets.

## What goes into your thesis Chapter 4 (after running the gallery)

1. **Figure 4.X** — A single 4-panel image: Original + Grad-CAM++ + SHAP + LIME for one clear-spoof case
2. **Figure 4.Y** — Same layout for one clear-live case
3. **Figure 4.Z** — Same layout for one borderline / disagreement case
4. **Table 4.X** — Method comparison: mean compute time, qualitative interpretability rating, output format
5. **Practitioner survey results** (Chapter 5) — using these same images as stimulus material

## Swapping into the Streamlit app

After the gallery works, replace the mock `explain()` in `app/services/mock_model.py`
with a thin wrapper that calls these modules. The `XAIResult.overlay_png` field
is already byte-compatible with Streamlit's `st.image()`.

---

# Phase 5b — Faithfulness metrics (quantitative comparison)

The gallery answers *"do the explanations look reasonable?"* visually.
Faithfulness metrics answer *"which method is most truthful to the model
quantitatively?"* — directly addressing Research Question 2.

## Metrics implemented

| Metric | Direction | What it measures |
|---|---|---|
| **Deletion-AUC** | ↓ lower is better | Progressively remove the most-attributed pixels. Faster confidence drop = more faithful explanation. |
| **Insertion-AUC** | ↑ higher is better | Start blank, progressively insert important pixels. Faster recovery = more faithful explanation. |
| **Pearson / Spearman correlation** | per pair | Pairwise agreement between methods (1.0 = identical attribution rankings) |
| **IoU top-20%** | per pair | Overlap between the top-K% most-attributed pixels across methods |
| **Sparsity** | per method | Fraction of pixels with negligible attribution (higher = more focused explanation) |

## Run it

```cmd
python -m src.xai.compare --checkpoint checkpoints\resnet50_20260612_102208\best.pth --n 10
```

Or on the deployment-tier model:

```cmd
python -m src.xai.compare --checkpoint checkpoints\mobilenetv3_large_20260616_105902\best.pth --model mobilenetv3_large --n 10
```

Time budget: each image takes ~25s (MobileNetV3) or ~90s (ResNet50) total
including the three XAI computes + faithfulness metrics. So **10 images
≈ 4–15 minutes** depending on model.

## Output

Files land in `results/xai_compare/<tag>_<ts>/`:

| File | Use |
|---|---|
| `per_image.csv` | One row per (image, method). Every metric for every image. Detailed appendix table. |
| `summary.csv` + `summary.json` | **The headline table — mean ± SD per method.** Goes straight into thesis Chapter 4 as Table 4.X. |
| `cross_method.csv` | Per-image pairwise method correlations + IoU. |
| `cross_method_summary.csv` | **Mean cross-method agreement table.** Goes into thesis as Table 4.Y. |
| `curves_deletion.png` | **Figure 4.Z (deletion curves).** Three curves (one per method) with ±SD shading. Lower curve = more faithful. |
| `curves_insertion.png` | **Figure 4.W (insertion curves).** Higher curve = more faithful. |

## Interpretation cheatsheet

After the run, you'll see something like:

```
FAITHFULNESS SUMMARY  (thesis Table 4.X)
======================================================================
method   deletion_auc  ins_auc  sparsity  compute_ms
gradcam        0.281    0.643     0.412         120
shap           0.317    0.611     0.198        3210
lime           0.402    0.553     0.785        5180
```

Reading this:
- **Grad-CAM++ wins on deletion-AUC** (0.281 lowest) — when its highlighted pixels are removed, the model loses confidence fastest.
- **Grad-CAM++ wins on insertion-AUC** (0.643 highest) — its top pixels recover the prediction with the fewest "additions."
- **LIME wins on sparsity** (0.785) — its explanations are the most concentrated (fewest important pixels).
- **Grad-CAM++ wins on compute time** (120 ms) by ~30×.

A thesis paragraph writes itself:

> *"Across 10 test images, Grad-CAM++ achieved the lowest deletion-AUC
> (0.281 ± 0.04) and highest insertion-AUC (0.643 ± 0.06), indicating the
> most faithful attribution to the model's decision boundary. SHAP was
> close on both metrics (0.317 / 0.611) but with 27× higher compute cost.
> LIME produced the sparsest explanations (78% of pixels below 5% peak
> attribution) but the lowest faithfulness scores, consistent with the
> superpixel quantization introducing artifacts not present in the model's
> own representation. The IoU at top-20% between Grad-CAM++ and SHAP was
> 0.52, indicating moderate agreement on which regions are important
> despite the methods' different theoretical foundations."*

## When to use this for the practitioner survey

The faithfulness CSV is your **objective evidence** that backs up the
subjective practitioner ratings. In thesis Chapter 5 you can write:

> *"Practitioner trust ratings for Grad-CAM++ (mean X / 5) align with the
> objective faithfulness metrics from Chapter 4.5: the method with the
> highest deletion-AUC performance also received the highest practitioner
> trust score. The agreement between objective and subjective evaluations
> strengthens the conclusion that Grad-CAM++ is the appropriate primary
> XAI method for forensic spoof-detection reporting."*

That's a defensible Chapter 5 paragraph linking RQ2 and RQ3 quantitatively.

## Flags

| Flag | Default | When to use |
|---|---|---|
| `--n 10` | 10 | Number of images. 20+ tightens the SD; expensive |
| `--steps 20` | 20 | Resolution of deletion/insertion curves. 50 = smoother but 2.5× slower |
| `--lime-samples 500` | 500 | Lower than gallery default for speed during metric runs |
| `--shap-bg 16` | 16 | SHAP background set size |
| `--skip lime` | — | Faster iteration when prototyping |
| `--tag mygallery` | checkpoint folder | Custom output folder name |

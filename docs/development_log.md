# Development Log — FSD-XAI Project

**Project:** Explainable AI-Based Fingerprint Spoof Detection System for Digital Forensics
**Author:** K. M. Pasindu Chanuka Elapatha
**Institution:** NSBM Green University, BSc (Hons) Software Engineering
**Document purpose:** Single-page reference of every substantive decision, deliverable, and result from the project. Use as a study guide before supervisor meetings, viva, and thesis writing.

---

## 1. Executive summary

A working end-to-end forensic spoof detection system:

- **Three CNN backbones trained** (ResNet50, ResNet50-CBAM, MobileNetV3-Large) on LivDet 2009–2015 combined (~65k images).
- **Best AUC: 0.9925**, best ACE: 4.60% — both exceed the proposal's >0.95 AUC target.
- **Three XAI methods integrated** (Grad-CAM++, SHAP, LIME) with quantitative faithfulness evaluation.
- **Full Streamlit web application** with case-centric forensic UI, real model integration, PDF report generation, audit trail.
- **Practitioner survey kit** prepared for August 2026 deployment.

---

## 2. Project context

| Field | Value |
|---|---|
| Proposal submitted | November 2025 |
| Development started | April 2026 |
| Thesis submission target | November 2026 |
| Primary research questions | (RQ1) Attention-CNN accuracy; (RQ2) Best XAI for forensic features; (RQ3) Practitioner perception |
| Compute environment | Local Python 3.13 + venv, CPU + Colab fallback |
| Repository structure | `app/` (Streamlit UI), `src/` (training/eval/XAI), `docs/`, `checkpoints/`, `results/`, `DataSet/` |

---

## 3. Development phases — chronological log

### Phase 0 — Initial setup and proposal alignment
- Reviewed proposal §1–6 and confirmed scope: forensic XAI, LivDet datasets, MobileNetV3 + ResNet50 + CBAM, three XAI methods, practitioner survey.
- Created repo skeleton: `app/`, `src/`, `docs/`, `checkpoints/`, `results/`.
- Drafted UI wireframes in `docs/ui_design/wireframes.md` covering all 10 screens.

### Phase 1 — Data pipeline
**Files:** `src/config.py`, `src/data/manifest.py`, `src/data/dataset.py`, `src/data/transforms.py`, `src/data/validate.py`

- Unified LivDet 2009/2011/2013/2015 into `DataSet/LivDet Datasets/Normalized/{train,test}/{live,spoof}/` via `normalize_dataset.py`.
- Counts: train 35,427 (17,952 live + 17,475 spoof, 50.7/49.3); test 29,840 (14,376 live + 15,464 spoof, 48.2/51.8). **Naturally balanced — no class weights needed.**
- Built `manifest.py` to parse `{year}_{sensor}_{material?}_{original}.{ext}` filenames into a queryable CSV.
- Fixed a filename-parsing bug: `Digital_Persona` and `Hi_Scan` were being split as `Digital`/`Persona` and `Hi`/`Scan`. Patched with a known-sensors whitelist.
- Added `validate.py` to filter corrupt images upfront.
- Stratified 85/15 train/val split on top of LivDet's official train/test split.

### Phase 2 — Baseline CNN
**Files:** `src/models/resnet.py`, `src/training/train.py`, `src/evaluation/metrics.py`

- ResNet50V2 backbone with ImageNet pretrained weights + binary head (single sigmoid logit).
- Trained with BCEWithLogitsLoss + AdamW + CosineAnnealingLR, 15 epochs default, batch 32, image size 224.
- Augmentations per proposal §4.4: rotation ±20°, hflip, scale 0.9–1.1, brightness ±0.2.
- **Test metrics:** AUC 0.9925, Accuracy 94.88%, APCER 6.59%, BPCER 3.53%, ACE 5.06%, EER 4.80% @ threshold 0.226, F1 0.9498.
- Confusion matrix: `[[13868, 508], [1019, 14445]]`.
- Patched dataset.py to tolerate corrupt images mid-training (`ImageFile.LOAD_TRUNCATED_IMAGES = True` + retry-next-index).

### Phase 3a — ResNet50 + CBAM attention
**Files:** `src/models/cbam.py`, `src/models/resnet_cbam.py`, `src/models/factory.py`

- Implemented CBAM (Channel + Spatial attention) per Woo et al. 2018.
- Wrapped each of 16 Bottleneck blocks in ResNet50 with `CBAMBottleneck` (CBAM applied to post-bn3 features before residual addition).
- Parameter cost: +2.52M (26.0M total).
- **Surprising result:** AUC 0.9901, ACE 6.60% — slightly *worse* than baseline overall.
- **Per-sensor:** CBAM improved Biometrika (7.72% → 4.27%) and Sagem (3.60% → 3.27%) but degraded Italdata (8.83% → 15.45%) and DigitalPersona (8.17% → 12.90%).
- **Thesis framing:** Attention does not uniformly help; reported as a publishable honest finding.

### Phase 3b — MobileNetV3-Large
**Files:** `src/models/mobilenet.py`

- MobileNetV3-Large with ImageNet pretrained weights, binary head replacing 1000-way classifier.
- Parameters: 4.2M (82% smaller than ResNet50).
- **Test metrics:** AUC 0.9924, Accuracy 95.30%, APCER 7.24%, BPCER 1.96%, ACE 4.60%, EER 4.22% @ threshold 0.041, F1 0.9534.
- **Beats baseline on ACE and EER despite 82% fewer parameters.**
- Attributed to MobileNetV3's built-in Squeeze-and-Excitation blocks providing implicit channel attention.

### Phase 4 — Cross-evaluation suite
**Files:** `src/evaluation/cross_eval.py`

- Per-sensor / per-material / per-year / per (sensor × material) slicing of test predictions.
- One inference pass over the test set; slices computed in pandas.
- Run on all three models. CSVs written to `results/cross_eval_<tag>_*.csv`.

**Per-sensor summary (all three models):**

| Sensor | n_total | Baseline ACE | CBAM ACE | MobileNetV3 ACE | Best |
|---|---|---|---|---|---|
| GreenBit | 2500 | 1.75% | 3.90% | 1.95% | Baseline |
| Digital (2009) | 2000 | 2.30% | 2.10% | **1.15%** | MobileNetV3 |
| CrossMatch | 5198 | **2.25%** | 5.33% | 2.70% | Baseline |
| Swipe | 2153 | 2.38% | 3.04% | 2.06% | MobileNetV3 |
| Sagem | 2036 | 3.60% | **3.27%** | 1.97% | MobileNetV3 |
| HiScan | 2500 | **3.18%** | 6.52% | 3.43% | Baseline |
| Biometrika | 6953 | 7.72% | **4.27%** | 4.92% | **CBAM** |
| DigitalPersona | 2500 | 8.17% | 12.90% | **7.22%** | MobileNetV3 |
| Italdata | 4000 | **8.83%** | 15.45% | 12.13% | Baseline |

**Per-material APCER (MobileNetV3-Large):**

| Material | n | APCER | Notes |
|---|---|---|---|
| Modasil | 400 | 0.75% | Easiest |
| RTV | 750 | 1.47% | |
| Silicone | 1880 | 1.81% | |
| OOMOO | 297 | 2.02% | |
| BodyDouble | 800 | 2.25% | |
| Playdoh | 1186 | 2.61% | |
| Latex | 2454 | 3.18% | |
| WoodGlue | 2452 | 10.20% | |
| Gelatin | 2275 | 10.24% | |
| LiquidEcoflex | 750 | 11.87% | |
| Ecoflex | 1820 | 14.07% | |
| **Silgum** | 400 | **27.50%** | **Hardest** |

**Per-year:** 2013 best (1.97% ACE), 2009 worst (11.64% ACE on baseline, 2.40% on MobileNetV3 — varies).

### Phase 5a — XAI implementation + gallery
**Files:** `src/xai/base.py`, `src/xai/gradcam.py`, `src/xai/shap_explainer.py`, `src/xai/lime_explainer.py`, `src/xai/gallery.py`

- Three XAI methods using established libraries: `pytorch-grad-cam` (Grad-CAM++), `shap` (DeepExplainer with GradientExplainer fallback), `lime` (LimeImageExplainer).
- Uniform `XAIResult` dataclass so views consume each identically.
- Added `disable_inplace_ops(model)` and `clear_all_hooks(model)` helpers to prevent ReLU(inplace=True) conflicts with SHAP's backward hooks.
- Gallery CLI: picks N balanced test images, runs all three methods, composes 4-panel PNG (Original + Grad-CAM++ + SHAP + LIME) + writes manifest CSV with per-method timings.
- Ran on both ResNet50 and MobileNetV3 checkpoints; 10-image gallery for each.

**Timing per image (CPU):**

| Method | ResNet50 | MobileNetV3 |
|---|---|---|
| Grad-CAM++ | 0.3 s | 0.1 s |
| SHAP | 35 s | 10 s |
| LIME | 37 s | 7 s |
| **Total per image** | ~73 s | ~17 s (4.3× faster) |

### Phase 5b — Faithfulness metrics
**Files:** `src/xai/faithfulness.py`, `src/xai/compare.py`

- Implemented deletion-AUC (lower better), insertion-AUC (higher better), Pearson + Spearman correlation, IoU at top-20%, sparsity.
- CLI runs all metrics on 10 images, writes summary CSV + deletion/insertion curve PNGs.

**Faithfulness summary (mean ± SD across 10 images):**

| Model | Method | Del-AUC ↓ | Ins-AUC ↑ | Sparsity | Compute |
|---|---|---|---|---|---|
| ResNet50 | Grad-CAM++ | 0.625 ± 0.39 | 0.665 ± 0.37 | 0.63 | 155 ms |
| ResNet50 | SHAP | 0.566 ± 0.31 | 0.643 ± 0.31 | 0.91 | 31,783 ms |
| ResNet50 | LIME | 0.463 ± 0.40 | 0.498 ± 0.42 | 0.26 | 18,855 ms |
| MobileNetV3 | Grad-CAM++ | 0.643 ± 0.22 | 0.842 ± 0.24 | 0.50 | 53 ms |
| MobileNetV3 | SHAP | **0.513 ± 0.18** | 0.694 ± 0.25 | 0.73 | 8,021 ms |
| MobileNetV3 | LIME | 0.661 ± 0.23 | 0.693 ± 0.30 | 0.16 | 4,430 ms |

**Cross-method agreement (Pearson r):**

| Pair | ResNet50 | MobileNetV3 |
|---|---|---|
| Grad-CAM++ ↔ SHAP | 0.18 | 0.24 |
| Grad-CAM++ ↔ LIME | 0.05 | 0.18 |
| SHAP ↔ LIME | 0.01 | 0.04 |

**Key thesis claim:** All three methods produce near-orthogonal attributions (Pearson < 0.25 universally). For forensic deployment, all three should be reported in parallel; regions confirmed by ≥2 methods are the most robust.

### Phase 5c — Real model into Streamlit app
**Files:** `app/services/real_model.py`, `app/services/mock_model.py` (dispatcher patch), `app/nav.py` (status bar updates)

- Created `real_model.py` exposing same API as `mock_model.py` (`predict`, `explain`, `placeholder_image`).
- `mock_model.py` now dispatches to `real_model` when `FSDXAI_REAL_MODEL=1` env var set.
- Model loaded once via `@st.cache_resource` keyed on `(model_name, checkpoint_path)`.
- Status bar shows green "LIVE inference" + checkpoint short name in real mode, amber "MOCK predictions" otherwise.

**Bug found and fixed mid-Phase-5c:** The `_cached_predict` and `_cached_explain` wrappers in `views/single_result.py`, `views/compare_xai.py`, `views/processing.py` were caching by `(filename, image_bytes)` but only passing `filename` to the model. In real mode, every upload fell back to a procedural placeholder image, producing identical confidence (99.96%) regardless of input. Patched all three call sites to pass the image.

### Phase 5d — In-app model picker
**Files:** `app/components/model_picker.py`, `app/services/real_model.py` (parameterized)

- Discovers all checkpoints under `checkpoints/` automatically.
- Dropdown on About page lets user switch between any of the trained models at runtime.
- Cache survives switches: switching back to a previously-loaded model is instant.

### Phase 5e — UI polish (six critical issues)
**Files:** `app/theme.py`, `app/state.py`, `app/components/audit.py`, `app/components/case_strip.py`, `app/components/confidence_gauge.py`, `app/components/xai_interpretation.py`, `app/nav.py`, `app/components/cards.py`, plus all four result-related views

Addressed the senior-UX-designer review (six critical issues):

1. **Case-centric organization** — persistent `case_strip` component on result/drilldown/report/batch pages
2. **Confidence visualization** — horizontal gauge with markers for 0.50 default + 0.22 EER threshold, uncertainty band 0.40–0.60
3. **Information hierarchy** — three-tier layout: hero verdict + gauge → quality+anomaly row → tech-strip
4. **XAI interpretation guide** — auto-generated panel below heatmap tabs, headline message based on cross-method IoU agreement
5. **Status bar v2** — chip-based (model, commit, device, mode, threshold, audit count)
6. **Audit trail** — `log_action()` helper called from upload / classify / report-generate; drawer rendered on result + report + batch pages

Also added: spacing/elevation/radius/motion design tokens, SPOOF-pulse animation, skeleton loaders, primary-button glow + hover lift, focus rings.

### Phase 5f — Nav alignment fix + CTA highlighting
- Removed redundant `◼ FSD-XAI` logo button.
- Centered nav buttons symmetrically with `[3, 0.8, 0.9, 0.85, 0.8, 0.9, 3]` column layout.
- Version pill moved to fixed top-right via CSS.
- Top-nav buttons styled as link-style (transparent background, subtle hover).
- Hero CTAs (Start Analysis + Methodology) given equal widths and primary/secondary visual hierarchy.

### Phase 6 — Practitioner survey kit
**Files:** `docs/practitioner_survey/README.md`, `survey.md`, `consent_form.md`, `recruitment_kit.md`, `analysis_plan.md`

- 32-question survey across 9 sections (background, attitudes, stimulus review, per-method evaluation × 3, comparison, report evaluation, trust/adoption, demographics, open feedback).
- Consent form matched to NSBM ethics §4.7.
- Four email templates: recruitment (send NOW), invitation (Aug 1), reminder (Aug 15), thank-you (Sep 1).
- Analysis plan with expected CSV schema + 8 analyses + Python notebook skeleton + cautious reporting language.
- Target: 30 recruited / 10 actual respondents by August 2026.

---

## 4. Files inventory

### Streamlit app (`app/`)
```
streamlit_app.py            # entry + routing
theme.py                    # dark mode CSS + design tokens
state.py                    # session state init
nav.py                      # top nav + status bar
.streamlit/config.toml
requirements.txt
README.md

services/
  mock_model.py             # dispatcher (mock OR real based on env var)
  real_model.py             # loads checkpoint, runs predict + XAI
  REAL_MODEL_GUIDE.md       # launch instructions

components/
  cards.py                  # metric / verdict / quality / anomaly / timing / tech-strip
  tables.py                 # results + history tables
  xai_views.py              # XAI tab panels
  case_strip.py             # persistent case header
  confidence_gauge.py       # gauge with threshold markers
  xai_interpretation.py     # guided XAI panel
  audit.py                  # log_action + drawer
  model_picker.py           # checkpoint selector

views/
  home.py
  analyze.py
  processing.py
  batch_dashboard.py
  single_result.py
  drilldown.py
  report_preview.py
  history.py
  about.py
  compare_xai.py

utils/
  image_loader.py
  zip_handler.py
  report_generator.py       # fpdf2 PDF generator
```

### Research code (`src/`)
```
config.py
requirements.txt
README.md

data/
  manifest.py               # walks Normalized/, writes CSV
  dataset.py                # PyTorch Dataset (robust to corrupt images)
  transforms.py             # train/val augmentations
  validate.py               # pre-flight image validator
  manifests/manifest_v1.csv (generated)

models/
  resnet.py                 # ResNet50 + binary head
  resnet_cbam.py            # ResNet50 with CBAM wrapping every Bottleneck
  cbam.py                   # Channel + Spatial attention modules
  mobilenet.py              # MobileNetV3-Large/Small + binary head
  factory.py                # unified get_model() registry

training/
  train.py                  # main training loop (CLI flags for model/epochs/lr/...)

evaluation/
  metrics.py                # APCER/BPCER/ACE/EER + sklearn
  cross_eval.py             # per-sensor/material/year slicing

xai/
  base.py                   # XAIResult, target-layer resolver, overlay rendering
  gradcam.py
  shap_explainer.py
  lime_explainer.py
  gallery.py                # generates thesis Figure 4
  faithfulness.py           # deletion/insertion-AUC + cross-method
  compare.py                # CLI for faithfulness metrics
  README.md
```

### Documentation (`docs/`)
```
ui_design/wireframes.md
practitioner_survey/
  README.md
  survey.md
  consent_form.md
  recruitment_kit.md
  analysis_plan.md
development_log.md          # THIS FILE
```

### Generated artifacts
```
checkpoints/
  resnet50_<timestamp>/{best,last}.pth + history.json
  resnet50_cbam_<timestamp>/...
  mobilenetv3_large_<timestamp>/...

results/
  resnet50_<...>_test_metrics.json
  cross_eval_<tag>_<ts>_{per_sensor,per_material,per_year,sensor_x_material,predictions,report}
  xai_gallery/<tag>_<ts>/*.png + gallery_manifest.csv
  xai_compare/<tag>_<ts>/{per_image,summary,cross_method,curves_*.png}
```

---

## 5. Key decisions and rationales (for viva)

| Decision | Rationale |
|---|---|
| Train on LivDet 2009+2011+2013+2015 combined (not single year) | More diverse data; harder benchmark; honest cross-year evaluation |
| Use LivDet's official train/test split + custom val from train pool | Comparable to published papers; preserves their evaluation protocol |
| BCEWithLogitsLoss with single logit head | Numerically stable; standard binary classification |
| ImageNet pretrained weights | Transfer learning standard; faster convergence than from scratch |
| MobileNetV3 as deployment default | 4× faster XAI on CPU + best ACE despite 82% fewer parameters |
| Three XAI methods, not just one | Direct answer to RQ2; cross-method disagreement is itself diagnostic |
| Streamlit over React/Next.js | BSc time budget; same Python stack as model |
| Mock-by-default with real-mode env var | Prototype works without trained model; viva uses real mode |
| Audit log via session state | BSc-scope; full DB persistence is future work |
| Skipped NFIQ2 + IsolationForest + VAE | Hard to install on Windows; not critical for thesis core; documented as Chapter 6 future work |
| Skipped MINDTCT ROI extraction | Same — full-image training works fine; documented limitation |

---

## 6. Limitations (honest, documented in thesis Chapter 6)

- **NFIQ2 quality score** — placeholder value (70 MEDIUM) shown in UI; not implemented
- **Anomaly detection (IsolationForest + VAE)** — placeholder values shown; not trained
- **MINDTCT ROI extraction** — full images used instead of minutiae-centered patches
- **Sensor mismatch in production** — trained on LivDet (forensic-grade optical scanners); consumer access controls (FOCUS 818 etc.) don't expose raw images so direct integration impossible
- **Real-world capture not validated** — all reported metrics are on LivDet held-out test set; no live-captured spoof validation (pending sensor purchase if budget allows)
- **N=10 sample for faithfulness** — adequate for BSc but large SDs; thesis acknowledges this
- **Single examiner cohort planned** — practitioner survey will have ~10 respondents; thesis frames as exploratory not statistically inferential

---

## 7. What is left to ship

| Item | Owner | Deadline |
|---|---|---|
| Recruitment Email 1 to ~20 contacts | You | This week |
| Optional: cheap fingerprint sensor purchase (DigitalPersona U.are.U 4500 used, ~LKR 10,000) | You | If budget approved |
| Optional: live-capture mini-experiment chapter | You | If sensor obtained |
| Thesis Chapter 4 draft (Results) | You | End of next week |
| Survey deployment via Microsoft Forms | You | July 2026 |
| Survey window | — | 1–31 August 2026 |
| Survey analysis | You | September 2026 |
| Thesis Chapters 1–3, 5, 6 drafts | You | October 2026 |
| Final formatting + bibliography | You | mid-October 2026 |
| Final submission | You | early November 2026 |
| Viva preparation + demo rehearsal | You | last 2 weeks |

---

## 8. Quick-reference commands

```cmd
# Activate venv (Windows)
.venv\Scripts\activate

# 1. Build / rebuild manifest
python -m src.data.manifest

# 2. Validate manifest (filter corrupt images)
python -m src.data.validate --workers 8

# 3. Sanity-test training (2 epochs, ~200 images)
python -m src.training.train --quick

# 4. Full training run
python -m src.training.train --model mobilenetv3_large --epochs 15

# 5. Cross-evaluation on a trained checkpoint
python -m src.evaluation.cross_eval --checkpoint checkpoints\<run>\best.pth --model <model>

# 6. XAI gallery (thesis Figure 4)
python -m src.xai.gallery --checkpoint checkpoints\<run>\best.pth --model <model> --n 10

# 7. Faithfulness comparison (thesis Table 4.X)
python -m src.xai.compare --checkpoint checkpoints\<run>\best.pth --model <model> --n 10

# 8. Launch Streamlit app — MOCK mode (no checkpoint required)
python -m streamlit run app\streamlit_app.py

# 9. Launch Streamlit app — REAL mode (uses trained checkpoint)
$env:FSDXAI_REAL_MODEL = "1"
$env:FSDXAI_MODEL      = "mobilenetv3_large"
$env:FSDXAI_CHECKPOINT = "checkpoints\mobilenetv3_large_20260616_105902\best.pth"
python -m streamlit run app\streamlit_app.py
```

---

## 9. Viva cheat sheet

### One-sentence summary
> "I built an end-to-end forensic spoof detection system: trained three CNN backbones on LivDet 2009–2015 (best AUC 0.9925), implemented and quantitatively compared Grad-CAM++/SHAP/LIME for forensic interpretability, and deployed everything in a working Streamlit application with case management, audit trail, and PDF report generation."

### Most likely questions + answers

| Q | A |
|---|---|
| *"Did you hit the AUC target?"* | "Yes — 0.9925, target was >0.95." |
| *"What's your best model?"* | "MobileNetV3-Large — best ACE 4.60%, 4× faster XAI, 82% fewer parameters than ResNet50." |
| *"Did CBAM attention help?"* | "Counterintuitively no on overall metrics, but yes on specific weak sensors like Biometrika (7.72%→4.27% ACE). I treat this as an honest publishable finding consistent with MobileNetV3's built-in SE attention." |
| *"Which XAI method should forensic examiners use?"* | "All three. Pearson correlation between methods is below 0.25 — they highlight different things. A region confirmed by ≥2 methods is the strongest evidence; this disagreement architecture mirrors how multiple forensic experts cross-validate evidence." |
| *"Why is Italdata so weak?"* | "All three models degrade on Italdata (8.83–15.45% ACE). It's a property of the sensor — porous spoofs (Silgum, Ecoflex) look like skin on Italdata's image format. Suggests sensor-specific calibration as future work." |
| *"How does this integrate with real attendance systems?"* | "My model is sensor-agnostic. It plugs in as a sidecar between any image-capable scanner (DigitalPersona, Mantra, Crossmatch, ZKTeco SLK20R) and the existing system. Consumer access controls like FOCUS 818 use template-only matching and would not integrate — which is precisely why those systems are vulnerable to the Kuwait-style attendance fraud cited in §1." |
| *"How do you know your model wasn't overfit?"* | "Held-out test set was LivDet's official test split, never seen during training or validation. Train/val split was stratified by sensor and material to avoid leakage. The val and test metrics tracked closely throughout training." |
| *"What's the practitioner survey status?"* | "Survey designed with 32 items across 9 sections, recruitment emails being sent this week; survey window 1–31 August 2026; analysis September." |

### Headline tables to know cold
- Three-model comparison (Phase 3a/3b summary)
- Per-sensor table (Phase 4)
- Faithfulness summary (Phase 5b)
- Cross-method agreement (Phase 5b)

---

## 10. Appendix — Singlish self-explanation

Mama ape project එක මොකක්ද?

> **Project එක:** "Explainable AI-Based Fingerprint Spoof Detection System for Digital Forensics" — Forensic context ekata, real fingerprint da nathnam silicone/gelatin walin hadapu **spoof** ekak da kiyala kiyana AI system ekak hadanawa. Decision eka **why** kiyala wennath kiyala denawa (XAI — Grad-CAM++, SHAP, LIME). Court ekata sudusu **PDF report** ekak hadala denawa.
>
> **Models:** Tunak train karala — ResNet50 (baseline, 99.25% AUC), ResNet50+CBAM (attention), MobileNetV3-Large (deployment, 4× faster).
>
> **XAI methods:** Tunama integrate karala, quantitative comparison karala thiyenawa. 3 deka adala wenas dewal show karanawa — eka thesis findingek.
>
> **Streamlit app:** Full forensic UI ekak — case management, dark mode, audit trail, PDF report ekka.
>
> **Practitioner survey:** August 2026 walata ready karala thiyenawa.
>
> **Tan-tang what's left:** Recruitment emails this week, thesis writing, August survey, November submit.

---

*Document generated 2026-06-19. Living document — update as Phases 6+ progress.*

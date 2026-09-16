# FSD-XAI — Streamlit Frontend

Forensic-lab dark-mode Streamlit prototype for the **Explainable Fingerprint
Spoof Detection System for Digital Forensics** project (BSc Hons Software
Engineering — NSBM Green University).

This is the **UI prototype** — predictions and XAI heatmaps are mock-generated
so you can run, demo, and iterate on the interface before the real model is
trained. When the real model arrives, swap one file and the whole UI starts
using real predictions.

---

## Quick start

### 1. Install dependencies

From the `app/` folder:

```bash
pip install -r requirements.txt
```

(Tested with Python 3.10+ on Windows. Streamlit, Pillow, numpy, pandas,
matplotlib, fpdf2 — nothing exotic.)

### 2. Run

```bash
streamlit run streamlit_app.py
```

Open the URL it prints (usually http://localhost:8501).

### Offline recovery mode (no AWS account or login required)

If AWS storage or the previous application account is no longer available,
run this from the project root in PowerShell:

```powershell
.\scripts\run_local_offline.ps1
```

The launcher binds the app to `127.0.0.1`, signs in only the local computer as
the **Local Recovery Operator**, and writes new images, XAI heatmaps and reports
to the gitignored `storage_local/` folder. It does not restore objects that
were deleted from AWS; it lets you use and demonstrate the application safely
without AWS credentials or a `.env` file. It uses the project’s local
MobileNetV3 checkpoint by default; add `-Mock` if you only want the UI demo.

### 3. Try it

- **Home** → click "Start Analysis"
- **Single tab** → drop any PNG/JPG/BMP/TIFF, fill the case fields, click
  Start Analysis. You'll land on the Single Result page.
- **Batch tab** → drop a `.zip` containing multiple fingerprint images.
  Watch the progress page → Batch Dashboard.
- **Drill-down** → from the Batch Dashboard, pick an image and click "Open →"
- **Report Preview** → "Generate PDF" from any result page.
- **Compare** → top nav, or "Compare All" from a result page.

---

## File structure

```
app/
├── streamlit_app.py           # entry point + routing
├── theme.py                   # forensic-lab dark mode CSS
├── state.py                   # session state init / helpers
├── nav.py                     # top nav + status bar
├── requirements.txt
├── .streamlit/
│   └── config.toml            # base theme
│
├── views/                     # one file per screen (10 screens)
│   ├── home.py
│   ├── analyze.py
│   ├── processing.py
│   ├── batch_dashboard.py
│   ├── single_result.py
│   ├── drilldown.py
│   ├── report_preview.py
│   ├── history.py
│   ├── about.py
│   └── compare_xai.py
│
├── components/                # reusable UI pieces
│   ├── cards.py               # metric/verdict/quality/anomaly/timing cards
│   ├── tables.py              # results + history tables
│   └── xai_views.py           # XAI tab panels
│
├── services/
│   └── mock_model.py          # ⚠ swap with real model later
│
└── utils/
    ├── image_loader.py        # multi-format image loading
    ├── zip_handler.py         # in-memory zip extraction
    └── report_generator.py    # forensic PDF generator (fpdf2)
```

---

## Swapping in the real model

The mock predictor lives in [services/mock_model.py](services/mock_model.py)
and exposes two functions:

```python
def predict(filename: str, image: PIL.Image | None = None) -> dict:
    # returns {label, confidence, raw_score, material, nfiq2,
    # quality_tier, anomaly_score, known_pattern, vae_recon_error,
    # timing_ms, model}

def explain(filename: str, image: PIL.Image | None = None) -> dict:
    # returns {gradcam, shap, lime} where each value is
    # {image: png_bytes, faithfulness, localization_iou, compute_ms, summary}
```

When the real CNN + XAI pipeline is ready, drop in a new module with the
same `predict()` and `explain()` signatures and update the import in:

- [views/single_result.py](views/single_result.py)
- [views/processing.py](views/processing.py)
- [views/compare_xai.py](views/compare_xai.py)

(Or simply rewrite [services/mock_model.py](services/mock_model.py) in place.)

The UI does not need to change.

---

## What works in the prototype

- ✅ All 10 screens from `docs/ui_design/wireframes.md`
- ✅ Top nav with active-link highlighting
- ✅ Bottom status bar with model + commit + dataset provenance
- ✅ Forensic-lab dark mode palette (CSS injected)
- ✅ Single-image upload (PNG / JPG / JPEG / BMP / TIF / TIFF)
- ✅ Zip batch upload with format validation + ignore-counting
- ✅ Live processing progress bar with throughput, ETA, and rolling tail
- ✅ Filterable, sortable batch results table with 7 metric cards
- ✅ Drill-down with Prev / Next navigation
- ✅ XAI tabs (Grad-CAM++ / SHAP / LIME / All) with mock heatmaps
- ✅ Forensic PDF generation (fpdf2, 4 pages, downloadable)
- ✅ XAI Comparison page with quantitative metrics table
- ✅ History within session
- ✅ About / Methodology page with full citations

## What is NOT real yet (because mock model)

- ❌ Predictions — uses filename-seeded RNG for deterministic mock output
- ❌ Heatmaps — synthetic gaussians, not real attribution
- ❌ Faithfulness / IoU scores — mock ranges
- ❌ NFIQ2 quality — mock integers
- ❌ Anomaly detection — random scores
- ❌ History persistence — in-session only (refresh = clear)

These are the artifacts that the **research-side** code (model training,
real XAI, real evaluation) will replace.

---

## Color palette (forensic-lab dark mode)

| Token | Hex | Use |
|---|---|---|
| `bg.base` | `#0B0F14` | App background |
| `bg.surface` | `#141B23` | Cards, panels |
| `bg.elevated` | `#1C2530` | Modals, hover |
| `text.primary` | `#E6EDF3` | Body text |
| `text.secondary` | `#8B949E` | Labels |
| `accent.live` | `#3FB950` | Live verdicts |
| `accent.spoof` | `#F85149` | Spoof verdicts |
| `accent.warn` | `#D29922` | Warnings, low quality |
| `accent.info` | `#58A6FF` | Primary action |
| `accent.neutral` | `#A371F7` | XAI accents |

Heatmaps use **viridis** (colorblind-safe, scientifically standard).

---

## Hosting (later)

When ready to share with your supervisor or examiners:

1. Push the repo to GitHub.
2. Sign up at [HuggingFace Spaces](https://huggingface.co/spaces).
3. Create a new Space, choose Streamlit SDK.
4. Point it at your GitHub repo.
5. Done — public URL like `huggingface.co/spaces/<you>/fsd-xai`.

Free tier supports CPU-only inference, which is fine for a demo.

---

## Known limitations of the prototype

- Single-process Streamlit; not multi-user
- History is in-session only (use SQLite later if needed)
- PDF preview uses a base64-data iframe — works in Chrome/Edge, may be flaky in Firefox
- Tables are read-only (use `st.data_editor` if you want inline editing)
- Offline recovery mode deliberately skips sign-in but is bound to local host only

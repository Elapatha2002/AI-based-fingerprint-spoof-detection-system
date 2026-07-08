# Running the Streamlit app with the REAL model

By default the Streamlit app shows **mock** predictions (filename-seeded
random outputs) so it runs without any trained checkpoint. This guide
shows how to switch it to use your actual trained model and XAI methods.

---

## Quick start — Windows / PowerShell

From the **project root**:

```cmd
cd "D:\Projects\University\Final year Resarch project"

$env:FSDXAI_REAL_MODEL = "1"
$env:FSDXAI_MODEL      = "mobilenetv3_large"
$env:FSDXAI_CHECKPOINT = "checkpoints\mobilenetv3_large_20260616_105902\best.pth"

python -m streamlit run app\streamlit_app.py
```

The status bar at the bottom should turn from amber ("MOCK predictions")
to green ("LIVE inference") with the checkpoint name shown.

---

## Quick start — CMD / Bash

CMD:
```cmd
set FSDXAI_REAL_MODEL=1
set FSDXAI_MODEL=mobilenetv3_large
set FSDXAI_CHECKPOINT=checkpoints\mobilenetv3_large_20260616_105902\best.pth
python -m streamlit run app\streamlit_app.py
```

Bash (Git Bash, WSL, Linux, macOS):
```bash
export FSDXAI_REAL_MODEL=1
export FSDXAI_MODEL=mobilenetv3_large
export FSDXAI_CHECKPOINT=checkpoints/mobilenetv3_large_20260616_105902/best.pth
python -m streamlit run app/streamlit_app.py
```

---

## Which checkpoint to use

| Mode | Recommended checkpoint | Why |
|---|---|---|
| **Demo / viva** | `mobilenetv3_large_20260616_105902` | 4× faster XAI on CPU (~17 s per image vs 73 s for ResNet50). Smooth demo. |
| **Thesis Chapter 4 screenshots** | `resnet50_20260612_102208` | Matches the baseline numbers in Chapter 4.1–4.3 |
| **Attention discussion** | `resnet50_cbam_20260612_145118` | If your viva specifically asks about CBAM |

Set `FSDXAI_MODEL` to the architecture matching the checkpoint:

| `FSDXAI_MODEL` value | Use with checkpoint folders starting with |
|---|---|
| `resnet50` | `resnet50_*` |
| `resnet50_cbam` | `resnet50_cbam_*` |
| `mobilenetv3_large` | `mobilenetv3_large_*` |
| `mobilenetv3_small` | `mobilenetv3_small_*` |

---

## What you'll see in real mode

| UI element | Real-mode behavior |
|---|---|
| Status bar | Green "LIVE inference" + checkpoint short name |
| Upload → Single Result | Real model verdict + confidence (takes ~1 s) |
| Single Result XAI tabs | **Real Grad-CAM++ / SHAP / LIME heatmaps** (~20–70 s first time) |
| Forensic Report PDF | Real predictions + real heatmaps embedded |
| Batch processing | Real per-image classification (still uses caching) |

The first explanation call on each image is slow (especially SHAP and LIME).
Subsequent re-opens are instant thanks to Streamlit's `@st.cache_data`.

---

## What is still mocked in real mode

These weren't part of the trained pipeline (proposal §4.4 mentions them
but they weren't implemented end-to-end yet — flag this in Chapter 6 as
future work):

- **NFIQ2 quality score** — shown as a placeholder mid-quality value
- **Anomaly detection** (IsolationForest + VAE) — shown with placeholder values
- **Per-image faithfulness scores** in XAI tabs — shown as reference values
  from the thesis study (the actual per-image faithfulness would add ~20
  extra forward passes per call, slowing the UI)

Everything else — verdict, confidence, material classification (from
filename), Grad-CAM++, SHAP, LIME, PDF report — is **real**.

---

## Troubleshooting

### "Checkpoint not found"

The path in `FSDXAI_CHECKPOINT` is wrong. Try with quotes:

```cmd
$env:FSDXAI_CHECKPOINT = "checkpoints\mobilenetv3_large_20260616_105902\best.pth"
```

Verify the path manually with `dir`.

### "Unknown model architecture"

You set `FSDXAI_MODEL` to a value other than the four allowed:
- `resnet50`
- `resnet50_cbam`
- `mobilenetv3_large`
- `mobilenetv3_small`

Check the spelling.

### "torch / torchvision not installed"

Switch to your training venv before launching Streamlit (the venv where
you trained the models). The real-model service needs the same PyTorch
that was used at training time.

```cmd
.venv\Scripts\activate
python -m streamlit run app\streamlit_app.py
```

### First XAI call hangs at 0%

Normal — SHAP DeepExplainer takes ~10 s on MobileNetV3 / 30 s on ResNet50
without any progress reporting. Be patient on the first explain() call.
LIME shows a progress bar; SHAP doesn't.

### Status bar shows "Real model error"

Something went wrong loading the checkpoint. Hover or check the terminal
running streamlit for the full traceback.

---

## Demo recipe for the viva

1. Before the viva, **warm up the model cache**: launch Streamlit, upload
   one image, generate the report. This loads PyTorch + the checkpoint
   into memory and computes one round of XAI. Subsequent demos are fast.
2. Have **3–4 sample fingerprint files ready on the desktop**: pick from
   your `DataSet\LivDet Datasets\Normalized\test\`. One clear spoof, one
   clear live, one borderline.
3. **Don't switch checkpoints mid-demo.** Pick one (MobileNetV3-Large
   recommended) and stay there.
4. If the network is unreliable, run Streamlit locally (`localhost:8501`)
   so it doesn't need internet.

---

## Reverting to mock mode

Just unset the env var and relaunch:

```cmd
Remove-Item Env:FSDXAI_REAL_MODEL
python -m streamlit run app\streamlit_app.py
```

The status bar returns to amber "MOCK predictions" and the prototype
runs without needing PyTorch.

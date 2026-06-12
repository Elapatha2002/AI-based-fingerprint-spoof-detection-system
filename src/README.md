# Training pipeline — Phase 1 + 2

Baseline ResNet50V2 fingerprint spoof classifier on your normalized LivDet
2009/2011/2013/2015 dataset. End-to-end runnable today; CBAM, MobileNetV3,
and XAI come in later phases.

## Folder map

```
src/
├── config.py                # paths, hyperparams, seeds
├── requirements.txt         # PyTorch + sklearn + pandas
├── data/
│   ├── manifest.py          # walks Normalized/, writes manifest_v1.csv
│   ├── dataset.py           # PyTorch Dataset reading from manifest
│   ├── transforms.py        # train/val augmentations
│   └── manifests/           # generated CSVs land here
├── models/
│   └── resnet.py            # ResNet50 + binary head
├── training/
│   └── train.py             # main training loop
└── evaluation/
    └── metrics.py           # APCER/BPCER/ACE/EER + sklearn metrics
```

Sibling folders at project root:
```
checkpoints/                 # trained model weights (.pth)
results/                     # test metrics JSONs
```

---

## Step 0 — Install PyTorch

PyTorch is heavy (~2 GB) and depends on whether you have an NVIDIA GPU.

### If you have NVIDIA GPU (recommended)
Visit https://pytorch.org/get-started/locally/, copy the install command for your CUDA version. Example for CUDA 12.x on Windows:

```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### If you only have CPU (works, but slow)
```
pip install torch torchvision
```

Then the rest:
```
pip install -r src/requirements.txt
```

Quick check:
```
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

---

## Step 1 — Build the manifest CSV

This walks `DataSet/LivDet Datasets/Normalized/` and produces one CSV
that every other script consumes. It also creates a stratified
85/15 train/val split out of the official 'train' pool. The official
'test' pool is held out unchanged.

```
python -m src.data.manifest
```

You should see something like:

```
Walking .../Normalized/train ...
  found 35,427 images
Walking .../Normalized/test ...
  found 29,840 images

MANIFEST SUMMARY
============================================================
  train   total 30,113   live 15,259   spoof 14,854   ratio 0.507
  val     total  5,314   live  2,693   spoof  2,621   ratio 0.507
  test    total 29,840   live 14,376   spoof 15,464   ratio 0.482
```

Output files:
- `src/data/manifests/manifest_v1.csv`
- `src/data/manifests/splits_v1.json`

---

## Step 2 — Quick sanity check (1–2 minutes on CPU, seconds on GPU)

Before committing to a full run, prove the pipeline works end-to-end with
a tiny subset:

```
python -m src.training.train --quick
```

This trains on ~200 images for 2 epochs. Numbers will be garbage; that's
fine. What you're checking:

- ✅ Manifest loads
- ✅ Images decode (TIFF/BMP/PNG/JPG all handled)
- ✅ Model forward pass works
- ✅ Loss decreases (a tiny bit)
- ✅ Test metrics print without crashing

If this passes, you can confidently launch a full run.

---

## Step 3 — Full training

```
python -m src.training.train --epochs 15
```

Defaults from the proposal:
- ResNet50V2 with ImageNet weights
- Batch size 32
- LR 3e-4, AdamW, cosine schedule
- BCEWithLogitsLoss
- 224×224 input
- Augmentations: rotation ±20°, hflip, scale 0.9–1.1×, brightness ±0.2
- Early stop after 4 epochs of no val-AUC improvement

Expected runtime per epoch:
- T4 GPU on Colab: ~10–15 min
- RTX 3060 / 4060 local: ~6–10 min
- CPU: ~3–6 hours (don't)

Outputs:
- `checkpoints/resnet50_<timestamp>/best.pth`
- `checkpoints/resnet50_<timestamp>/last.pth`
- `checkpoints/resnet50_<timestamp>/history.json`
- `results/resnet50_<timestamp>_test_metrics.json`

The final test metrics print at the end:
```
TEST METRICS (best ckpt):
  AUC      : 0.978
  Accuracy : 0.943
  APCER    : 4.21%
  BPCER    : 6.85%
  ACE      : 5.53%
  EER      : 5.40%  @ thr=0.487
  F1       : 0.946
  CM       : [[13392, 984], [1314, 14150]]
```

This is the headline table for your thesis Chapter 4.

---

## Common flags

| Flag | Effect |
|---|---|
| `--quick` | 200 samples, 2 epochs — sanity check only |
| `--epochs 20` | Override epochs (default 15) |
| `--lr 2e-4` | Override learning rate |
| `--batch 16` | Smaller batch (use if OOM on small GPU) |
| `--freeze` | Train only the classifier head (faster, lower ceiling) |
| `--tag exp1` | Custom name for the checkpoint folder |

---

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `CUDA out of memory` | Batch too big for GPU | `--batch 16` or `--batch 8` |
| `Could not decode image` | Corrupt file in dataset | Note the filename; safe to ignore single bad files |
| `Manifest not found` | Skipped Step 1 | Run `python -m src.data.manifest` |
| `ModuleNotFoundError: src` | Running from wrong dir | Run from project root, not from `src/` |
| Slow on CPU | No GPU | Use Colab — see notebooks/ (next phase) |

---

## Running on Google Colab

This codebase works in Colab without changes. In a Colab cell:

```python
from google.colab import drive
drive.mount('/content/drive')

%cd "/content/drive/MyDrive/Final year Resarch project"
!pip install -q -r src/requirements.txt

# Override DATA_ROOT if needed by editing src/config.py for the Colab path

!python -m src.data.manifest
!python -m src.training.train --epochs 15
```

Tip: put the `DataSet/` folder in your Google Drive once. Subsequent runs
skip re-uploading.

---

## What's next (Phase 3+)

1. **CBAM attention** added to ResNet50 — `src/models/cbam.py`
2. **MobileNetV3** alternative backbone — `src/models/mobilenet.py`
3. **Cross-sensor evaluation** — train on Biometrika, test on CrossMatch
4. **Cross-year evaluation** — train on 2013, test on 2015
5. **Per-material breakdown** — which spoof materials are hardest
6. **Optuna hyperparameter search**
7. **Grad-CAM++, SHAP, LIME wrappers** (`src/xai/`)
8. **Real model service** that drops into the Streamlit app

Ping me to start Phase 3 when this one trains successfully.

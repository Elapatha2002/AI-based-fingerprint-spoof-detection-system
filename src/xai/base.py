"""
Common helpers shared across XAI methods.

  - Target-layer resolution per backbone (where Grad-CAM hooks attach)
  - Image preprocessing matching the training pipeline
  - Overlay rendering (heatmap on top of original) via matplotlib
  - A common XAIResult dict schema so the gallery script can iterate uniformly

Designed so that each XAI module (gradcam / shap / lime) returns the same
shape — making it trivial to drop into the Streamlit app's `mock_model.explain()`.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass, asdict
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

import matplotlib
matplotlib.use("Agg")        # safe in headless / CPU-only runs
import matplotlib.pyplot as plt

from src.data.transforms import eval_transform, IMAGENET_MEAN, IMAGENET_STD


@dataclass
class XAIResult:
    """Uniform return value across Grad-CAM++ / SHAP / LIME."""
    method: str                       # 'gradcam' | 'shap' | 'lime'
    heatmap: np.ndarray               # (H, W) normalized to [0, 1] or [-1, 1] for SHAP
    overlay_png: bytes                # ready-to-display PNG with heatmap over original
    compute_ms: int                   # wall-clock time for the explanation
    summary: str                      # one-line plain-language description
    extra: dict | None = None         # method-specific metadata (e.g. LIME superpixel ids)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["heatmap"] = self.heatmap.tolist()  # JSON-friendly if dumped
        return d


# ─────────────────────────────────────────────────────────────────────────
# Target layer resolution
# ─────────────────────────────────────────────────────────────────────────

def disable_inplace_ops(model: nn.Module) -> nn.Module:
    """
    Walk the module tree and turn off any inplace flag.

    Why: SHAP DeepExplainer and Grad-CAM++ both register backward hooks.
    PyTorch refuses to differentiate through `ReLU(inplace=True)` (and
    similar `Hardswish`, `ReLU6`, `SiLU` variants with `inplace=True`)
    when a custom backward hook is attached — it raises the
    "view + inplace + custom Function" error.

    Disabling inplace here is safe: it slightly increases memory usage
    during the forward pass, but the model's outputs are mathematically
    identical. Apply once after loading the checkpoint, before any XAI
    method runs.
    """
    for m in model.modules():
        if hasattr(m, "inplace"):
            m.inplace = False
    return model


def clear_all_hooks(model: nn.Module) -> None:
    """
    Forcibly remove every forward / backward / forward-pre hook on every
    submodule. Used between XAI methods so a partially-failed explainer
    cannot contaminate the next one.
    """
    for m in model.modules():
        for attr in ("_forward_hooks", "_backward_hooks",
                     "_forward_pre_hooks", "_full_backward_hooks",
                     "_full_backward_pre_hooks"):
            d = getattr(m, attr, None)
            if isinstance(d, dict):
                d.clear()


def get_target_layer(model: nn.Module, model_name: str) -> nn.Module:
    """
    Return the conv layer Grad-CAM++ should hook into.

    For ResNet50 / ResNet50-CBAM:  last Bottleneck of layer4
    For MobileNetV3:               last conv block in features
    """
    if model_name.startswith("resnet50"):
        return model.layer4[-1]
    if model_name.startswith("mobilenetv3"):
        return model.features[-1]
    raise ValueError(f"Unknown model name for target layer: {model_name!r}")


# ─────────────────────────────────────────────────────────────────────────
# Image preprocessing
# ─────────────────────────────────────────────────────────────────────────

_EVAL_TF = eval_transform()


def preprocess(pil_img: Image.Image) -> torch.Tensor:
    """PIL → (1, 3, 224, 224) normalized tensor matching training."""
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    return _EVAL_TF(pil_img).unsqueeze(0)


def tensor_to_rgb01(tensor: torch.Tensor) -> np.ndarray:
    """Un-normalize a (3, H, W) preprocessed tensor back to (H, W, 3) in [0, 1].
    Used so we can paint heatmaps on top of the original RGB."""
    arr = tensor.detach().cpu().numpy().transpose(1, 2, 0)
    arr = arr * np.array(IMAGENET_STD) + np.array(IMAGENET_MEAN)
    return np.clip(arr, 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────
# Heatmap overlay rendering
# ─────────────────────────────────────────────────────────────────────────

def make_overlay_png(rgb01: np.ndarray, heatmap: np.ndarray,
                     cmap: str = "viridis", alpha: float = 0.5,
                     title: str = "") -> bytes:
    """
    Compose a heatmap overlay onto the RGB image and return the PNG bytes.

    Args:
        rgb01:    (H, W, 3) in [0, 1]
        heatmap:  (H', W'), will be resized to match rgb01 if needed
        cmap:     'viridis' (default) for unsigned, 'RdBu_r' for signed (SHAP)
        alpha:    heatmap opacity [0, 1]
        title:    optional caption below the image
    """
    H, W = rgb01.shape[:2]
    if heatmap.shape != (H, W):
        # Resize heatmap to image resolution using PIL nearest-neighbor
        hm = Image.fromarray((heatmap * 255).astype(np.uint8) if heatmap.max() > 1
                             else (heatmap * 255).astype(np.uint8))
        hm = np.array(hm.resize((W, H), Image.BILINEAR)) / 255.0
    else:
        hm = heatmap

    fig, ax = plt.subplots(figsize=(3.0, 3.0), dpi=120)
    ax.imshow(rgb01)
    if cmap == "RdBu_r":
        # signed attribution: center colormap on zero
        vmax = float(np.abs(hm).max()) + 1e-8
        ax.imshow(hm, cmap=cmap, alpha=alpha, vmin=-vmax, vmax=vmax)
    else:
        ax.imshow(hm, cmap=cmap, alpha=alpha)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=10, color="white", pad=4)
    fig.patch.set_facecolor("#0B0F14")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                pad_inches=0.05, facecolor="#0B0F14")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────
# Timing helper
# ─────────────────────────────────────────────────────────────────────────

class Timer:
    """Context manager: `with Timer() as t: ...` then `t.ms` is wall-clock ms."""

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *_):
        self.ms = int((time.time() - self.t0) * 1000)


# ─────────────────────────────────────────────────────────────────────────
# Common attribution summary text
# ─────────────────────────────────────────────────────────────────────────

def attribution_summary(heatmap: np.ndarray, method: str) -> str:
    """One-line plain-English description of where attribution concentrates."""
    H, W = heatmap.shape
    abs_map = np.abs(heatmap)
    if abs_map.sum() == 0:
        return f"{method}: no significant attribution detected."

    # Find the centroid of attribution mass
    ys, xs = np.indices((H, W))
    cy = (ys * abs_map).sum() / abs_map.sum()
    cx = (xs * abs_map).sum() / abs_map.sum()

    h3 = H / 3
    w3 = W / 3
    v = "top" if cy < h3 else "middle" if cy < 2 * h3 else "bottom"
    h = "left" if cx < w3 else "center" if cx < 2 * w3 else "right"
    peak = float(np.abs(heatmap).max())

    return (f"{method}: attribution concentrated in the {v}-{h} region "
            f"(peak {peak:.2f}).")

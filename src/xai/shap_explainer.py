"""
SHAP DeepExplainer wrapper.

Reference: Lundberg & Lee (2017), "A Unified Approach to Interpreting
Model Predictions."

DeepExplainer computes approximate Shapley values via gradient
backpropagation against a *background distribution* — a small set of
"reference" images that represent baseline activations. The resulting
attribution map shows which input pixels push the prediction toward
"spoof" (positive) vs. toward "live" (negative).

Notes
-----
- DeepExplainer expects a model that returns a 2D tensor (B, C). For our
  single-logit binary head, we wrap the model so it outputs (B, 2) using
  [-logit, +logit] — this gives SHAP a "live channel" and "spoof channel"
  to attribute against.
- Background = 16 random TRAIN images by default. More is fancier but
  slower; 16 is the sweet spot on CPU.
- DeepExplainer is the slowest of the three XAIs on CPU (~3–10 s/image).
"""
from __future__ import annotations

import random
import numpy as np
import torch
import torch.nn as nn
from PIL import Image

import shap

from src.xai.base import (
    XAIResult, Timer,
    preprocess, tensor_to_rgb01, make_overlay_png, attribution_summary,
    disable_inplace_ops, clear_all_hooks,
)
from src.data.dataset import load_manifest, FingerprintDataset
from src.data.transforms import eval_transform


# ─────────────────────────────────────────────────────────────────────────
# Wrap binary-head model so SHAP sees two output classes
# ─────────────────────────────────────────────────────────────────────────

class _TwoClassWrapper(nn.Module):
    """Convert single-logit binary head → (B, 2) two-class output.

    Column 0 = -logit ('live' side)
    Column 1 = +logit ('spoof' side)
    """
    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x):
        logit = self.model(x)              # (B, 1)
        return torch.cat([-logit, logit], dim=1)


# ─────────────────────────────────────────────────────────────────────────
# Background images (cached across calls)
# ─────────────────────────────────────────────────────────────────────────

_BG_CACHE: dict[int, torch.Tensor] = {}


def _build_background(n: int = 16) -> torch.Tensor:
    """Sample `n` random TRAIN images, preprocessed, stacked as (n, 3, H, W)."""
    if n in _BG_CACHE:
        return _BG_CACHE[n]

    df = load_manifest()
    ds = FingerprintDataset(df, "train", eval_transform())
    indices = random.sample(range(len(ds)), min(n, len(ds)))
    tensors = [ds[i][0] for i in indices]
    bg = torch.stack(tensors)
    _BG_CACHE[n] = bg
    return bg


# ─────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────

def explain(model: nn.Module, image: Image.Image, model_name: str,
            device: torch.device | None = None,
            background_n: int = 16,
            target_class: int = 1) -> XAIResult:
    """
    Run SHAP DeepExplainer. Returns spatial attribution heatmap.

    Args:
        model:         trained nn.Module (binary head)
        image:         PIL.Image
        model_name:    unused here but kept in signature for uniformity
        device:        optional torch.device
        background_n:  size of the background distribution. More is fancier
                       but slower. 16 is a CPU-friendly default.
        target_class:  0 = explain 'live', 1 = explain 'spoof' (default).
    """
    if device is None:
        device = next(model.parameters()).device
    model.eval()
    disable_inplace_ops(model)             # SHAP cannot tolerate inplace ReLU

    wrapped = _TwoClassWrapper(model).to(device).eval()
    background = _build_background(background_n).to(device)
    input_tensor = preprocess(image).to(device)

    used_method = "DeepExplainer"
    try:
        with Timer() as t:
            try:
                explainer = shap.DeepExplainer(wrapped, background)
                shap_values = explainer.shap_values(
                    input_tensor, check_additivity=False
                )
            except Exception as deep_err:
                # Fall back to gradient-based explainer — simpler, no custom hooks.
                # Slightly less accurate but works on any architecture.
                clear_all_hooks(wrapped)
                used_method = f"GradientExplainer (fallback: {type(deep_err).__name__})"
                explainer = shap.GradientExplainer(wrapped, background)
                shap_values = explainer.shap_values(input_tensor)
    finally:
        # No matter what happened, leave the model clean for the next XAI method
        clear_all_hooks(wrapped)
        clear_all_hooks(model)

    # shap_values shape handling — varies by SHAP version:
    #   list of arrays per class → shap_values[target_class]: (1,3,H,W)
    #   single array (1, 3, H, W, 2)
    if isinstance(shap_values, list):
        attr = shap_values[target_class][0]      # (3, H, W)
    else:
        attr = shap_values[0, :, :, :, target_class]  # (3, H, W)

    # Sum channel attributions → (H, W) spatial map
    spatial = attr.sum(axis=0).astype(np.float32)

    # Symmetric normalize to [-1, 1] so the diverging colormap reads sensibly
    vmax = float(np.abs(spatial).max()) + 1e-8
    norm = spatial / vmax

    rgb = tensor_to_rgb01(input_tensor.squeeze(0))
    overlay_png = make_overlay_png(rgb, norm, cmap="RdBu_r",
                                   alpha=0.55, title="SHAP")
    summary = attribution_summary(norm, "SHAP")

    return XAIResult(
        method="shap",
        heatmap=norm,
        overlay_png=overlay_png,
        compute_ms=t.ms,
        summary=summary,
        extra={"target_class": target_class,
               "background_n": background_n,
               "max_abs": vmax,
               "explainer": used_method},
    )

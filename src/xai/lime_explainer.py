"""
LIME (Local Interpretable Model-agnostic Explanations) wrapper.

Reference: Ribeiro et al. (2016), "Why Should I Trust You? Explaining
the Predictions of Any Classifier."

LIME splits the image into superpixels, perturbs them, queries the model,
and fits a sparse linear surrogate. The output is a small set of
"important" superpixels — much more localized than gradient methods.

Notes
-----
- LIME needs a classifier_fn that takes (N, H, W, 3) uint8 and returns
  (N, num_classes) probabilities. We adapt our binary head accordingly.
- On CPU this is slow: ~10–20 s/image with 1000 perturbations. Reduce
  `num_samples` for faster iteration (default here = 800, paper uses 5000).
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from lime.lime_image import LimeImageExplainer

from src.xai.base import (
    XAIResult, Timer,
    preprocess, tensor_to_rgb01, make_overlay_png, attribution_summary,
)
from src.data.transforms import eval_transform


# ─────────────────────────────────────────────────────────────────────────
# Classifier function bridge (LIME ↔ PyTorch)
# ─────────────────────────────────────────────────────────────────────────

def _make_classifier_fn(model: nn.Module, device: torch.device):
    eval_tf = eval_transform()

    def classify(images_np: np.ndarray) -> np.ndarray:
        """images_np: (N, H, W, 3) uint8 → returns (N, 2) probs."""
        batch = torch.stack([
            eval_tf(Image.fromarray(img.astype(np.uint8)))
            for img in images_np
        ]).to(device)
        with torch.inference_mode():
            logits = model(batch).cpu().numpy().flatten()
        # Sigmoid → P(spoof); we expose live + spoof as 2 columns
        p_spoof = 1.0 / (1.0 + np.exp(-logits))
        p_live = 1.0 - p_spoof
        return np.stack([p_live, p_spoof], axis=1)

    return classify


# ─────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────

def explain(model: nn.Module, image: Image.Image, model_name: str,
            device: torch.device | None = None,
            num_samples: int = 800,
            num_features: int = 5,
            target_class: int = 1) -> XAIResult:
    """
    Run LIME on the given image.

    Args:
        model:        trained binary classifier
        image:        PIL.Image
        model_name:   unused (uniform signature)
        device:       optional torch.device
        num_samples:  number of perturbed neighbours to evaluate.
                      800 = ~10–20s on CPU. 5000 = paper default but very slow.
        num_features: number of superpixels to highlight as 'important'.
        target_class: 0 = live, 1 = spoof. Default explains the spoof score.
    """
    if device is None:
        device = next(model.parameters()).device
    model.eval()

    # LIME works on the IMAGE PIXELS directly (not preprocessed tensor)
    # so we feed it the resized 224x224 RGB array.
    img_rgb = image.convert("RGB").resize((224, 224), Image.BILINEAR)
    img_np = np.array(img_rgb)

    classifier_fn = _make_classifier_fn(model, device)
    explainer = LimeImageExplainer()

    with Timer() as t:
        explanation = explainer.explain_instance(
            image=img_np,
            classifier_fn=classifier_fn,
            top_labels=2,
            hide_color=0,
            num_samples=num_samples,
            random_seed=42,
        )

    # Build a (H, W) heatmap from the top-k superpixel weights for target_class
    seg = explanation.segments                              # (224, 224) ints
    weights = dict(explanation.local_exp[target_class])     # {segment_id: weight}

    heatmap = np.zeros_like(seg, dtype=np.float32)
    for seg_id, w in weights.items():
        heatmap[seg == seg_id] = w

    # Symmetric normalize for diverging palette
    vmax = float(np.abs(heatmap).max()) + 1e-8
    norm = heatmap / vmax

    # Build overlay against the un-normalized RGB image
    rgb = np.asarray(img_rgb).astype(np.float32) / 255.0
    overlay_png = make_overlay_png(rgb, norm, cmap="RdBu_r",
                                   alpha=0.55, title="LIME")
    summary = attribution_summary(norm, "LIME")

    return XAIResult(
        method="lime",
        heatmap=norm,
        overlay_png=overlay_png,
        compute_ms=t.ms,
        summary=summary,
        extra={
            "target_class": target_class,
            "num_samples": num_samples,
            "num_top_superpixels": len(weights),
        },
    )

"""
Grad-CAM++ wrapper.

Reference: Chattopadhay et al. (2018), "Grad-CAM++: Improved Visual
Explanations for Deep Convolutional Networks."

Uses the maintained `pytorch-grad-cam` library so we get correct gradient
math and CAM normalization out of the box. Output is a (H, W) heatmap in
[0, 1] indicating spatial regions that contribute most to the predicted
class score.

For our binary spoof detector, we always explain the SINGLE OUTPUT logit
(P(spoof) before sigmoid). To explain "why live" instead of "why spoof,"
just negate the resulting heatmap.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from pytorch_grad_cam import GradCAMPlusPlus
from pytorch_grad_cam.utils.model_targets import RawScoresOutputTarget

from src.xai.base import (
    XAIResult, Timer,
    get_target_layer, preprocess, tensor_to_rgb01,
    make_overlay_png, attribution_summary,
    disable_inplace_ops, clear_all_hooks,
)


def explain(model: nn.Module, image: Image.Image, model_name: str,
            device: torch.device | None = None) -> XAIResult:
    """
    Run Grad-CAM++ on the given image. Returns an XAIResult.

    Args:
        model:      trained nn.Module (in eval mode is fine; we set it anyway)
        image:      PIL.Image, any size — will be preprocessed
        model_name: 'resnet50', 'resnet50_cbam', 'mobilenetv3_large', etc.
        device:     optional torch.device. Defaults to model's device.
    """
    if device is None:
        device = next(model.parameters()).device
    model.eval()
    disable_inplace_ops(model)             # Grad-CAM++ hooks need non-inplace ops
    clear_all_hooks(model)                 # in case a previous explainer left some

    input_tensor = preprocess(image).to(device)
    target_layer = get_target_layer(model, model_name)

    try:
        with Timer() as t:
            cam = GradCAMPlusPlus(model=model, target_layers=[target_layer])
            grayscale_cam = cam(
                input_tensor=input_tensor,
                targets=[RawScoresOutputTarget()],
            )[0]  # → (H, W) in [0, 1]
    finally:
        clear_all_hooks(model)

    rgb = tensor_to_rgb01(input_tensor.squeeze(0))
    overlay_png = make_overlay_png(rgb, grayscale_cam, cmap="viridis",
                                   alpha=0.55, title="Grad-CAM++")
    summary = attribution_summary(grayscale_cam, "Grad-CAM++")

    return XAIResult(
        method="gradcam",
        heatmap=grayscale_cam.astype(np.float32),
        overlay_png=overlay_png,
        compute_ms=t.ms,
        summary=summary,
    )

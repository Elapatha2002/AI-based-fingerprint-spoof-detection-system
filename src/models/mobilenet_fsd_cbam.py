"""
MobileNetV3-Large with FSD-CBAM wrapping the deepest InvertedResidual blocks.

This is the mobile-friendly companion to the ResNet50-based FSD-CBAM v2
model. It transfers the three architectural refinements identified as
useful for fingerprint spoof detection onto a lightweight backbone:

  1. Multi-scale channel attention (r = 8, 16) — same as v2.

  2. Focused spatial attention — 7 × 7 kernel on 14 × 14 feature maps,
     5 × 5 on 7 × 7 feature maps. Never global-in-space.

  3. Selective insertion at the deepest four InvertedResidual blocks
     only (indices 12, 13, 14, 15 of ``model.features``). Earlier
     blocks retain their pretrained representations untouched.

The wrapper preserves each block's built-in Squeeze-and-Excitation (SE)
gate rather than replacing it. FSD-CBAM operates on the block's output,
combining single-scale-channel (via SE, inside the block) with
multi-scale-channel + spatial gating (via FSD-CBAM, at the output).

MobileNetV3-Large deep-block shape reference (input 224 × 224 → 7 × 7):

    index    in_ch    out_ch   fmap   SE
    11       80       112      14x14  yes
    12       112      112      14x14  yes  ← wrapped
    13       112      160      7x7    yes  ← wrapped, downsample
    14       160      160      7x7    yes  ← wrapped
    15       160      160      7x7    yes  ← wrapped

At training time, the differential-learning-rate schedule in
``src/training/train.py`` gives FSD-CBAM parameters ten times the
learning rate of the pretrained trunk, matching the recipe used
successfully for FSD-CBAM v2 on ResNet50.
"""
from __future__ import annotations

import torch.nn as nn
from torchvision import models

from src.models.fsd_cbam import FSDCBAM


# Which blocks of model.features to wrap. Blocks 12-15 are the deepest
# four InvertedResidual blocks in MobileNetV3-Large; they operate on
# the smallest feature maps (14x14 and 7x7) and carry the most
# discriminative representations.
DEFAULT_INSERTION_INDICES = (12, 13, 14, 15)

# Documented output-channel counts for MobileNetV3-Large's deep blocks.
# Hardcoded rather than introspected because the InvertedResidual class
# does not expose out_channels directly, and the last Conv2d inside the
# block may belong to the SE branch rather than the main path.
BLOCK_OUT_CHANNELS = {
    12: 112,
    13: 160,
    14: 160,
    15: 160,
}

# Spatial-attention kernel size per block. Blocks 12 sits on a 14x14
# feature map (7x7 kernel covers 25% of the map — focused). Blocks
# 13-15 sit on 7x7 (5x5 kernel covers ~51% — focused, not global).
BLOCK_KERNEL = {
    12: 7,
    13: 5,
    14: 5,
    15: 5,
}


class InvertedResidualWithFSDCBAM(nn.Module):
    """Wraps a MobileNetV3 InvertedResidual and applies FSD-CBAM to its output.

    The wrapped block runs unchanged (its internal SE gate still fires).
    FSD-CBAM then gates the block output before it becomes the next
    block's input.
    """

    def __init__(self,
                 inverted_residual: nn.Module,
                 out_channels: int,
                 reduction_ratios: tuple[int, ...] = (8, 16),
                 spatial_kernel: int = 5):
        super().__init__()
        self.block = inverted_residual
        self.fsd_cbam = FSDCBAM(
            channels=out_channels,
            reduction_ratios=reduction_ratios,
            spatial_kernel=spatial_kernel,
        )

    def forward(self, x):
        return self.fsd_cbam(self.block(x))


def build_mobilenetv3_fsd_cbam(
        pretrained: bool = True,
        freeze_backbone: bool = False,
        insertion_indices: tuple[int, ...] = DEFAULT_INSERTION_INDICES,
        reduction_ratios: tuple[int, ...] = (8, 16),
) -> nn.Module:
    """Build MobileNetV3-Large with FSD-CBAM at the deepest blocks.

    Args:
        pretrained:         load ImageNet weights for the MobileNetV3 trunk
        freeze_backbone:    freeze everything except FSD-CBAM + classifier
        insertion_indices:  which ``model.features`` blocks to wrap
        reduction_ratios:   channel-attention MLP reduction ratios
    """
    for idx in insertion_indices:
        if idx not in BLOCK_OUT_CHANNELS:
            raise ValueError(
                f"insertion index {idx} not supported. "
                f"Known indices: {sorted(BLOCK_OUT_CHANNELS)}"
            )

    weights = (models.MobileNet_V3_Large_Weights.IMAGENET1K_V2
               if pretrained else None)
    model = models.mobilenet_v3_large(weights=weights)

    # Wrap the targeted InvertedResidual blocks in place.
    for idx in insertion_indices:
        original = model.features[idx]
        model.features[idx] = InvertedResidualWithFSDCBAM(
            inverted_residual=original,
            out_channels=BLOCK_OUT_CHANNELS[idx],
            reduction_ratios=reduction_ratios,
            spatial_kernel=BLOCK_KERNEL[idx],
        )

    if freeze_backbone:
        for name, p in model.named_parameters():
            if "fsd_cbam" in name or name.startswith("classifier"):
                p.requires_grad = True
            else:
                p.requires_grad = False

    # Replace the final 1000-way classifier with a single-logit binary head.
    # Matches the pattern used for build_mobilenetv3 so downstream code
    # (predict, XAI wrappers) needs no changes.
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, 1)

    return model

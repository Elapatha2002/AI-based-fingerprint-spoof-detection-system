"""
MobileNetV3 backbone with binary classification head.

Reference: Howard et al. (2019), "Searching for MobileNetV3," ICCV.

Per proposal §4.5, MobileNetV3 is the second backbone alongside ResNet50V2.
Use it for the speed/accuracy comparison table in your Chapter 4 — it's
roughly 1/10th the parameters of ResNet50 but reaches similar accuracy
on LivDet-style data.

Two sizes:
    'large'  ~5.5M params · slower · more accurate
    'small'  ~2.5M params · faster · slightly less accurate

For your forensic-lab use case, default to 'large'. The 'small' variant
exists for the embedded / mobile deployment discussion in Chapter 6.
"""
import torch.nn as nn
from torchvision import models


def build_mobilenetv3(pretrained: bool = True,
                     freeze_backbone: bool = False,
                     size: str = "large") -> nn.Module:
    """
    Build a MobileNetV3 with a single-logit binary head.

    Args:
        pretrained:      load ImageNet weights
        freeze_backbone: train classifier only
        size:            'large' (default) or 'small'
    """
    if size == "large":
        weights = (models.MobileNet_V3_Large_Weights.IMAGENET1K_V2
                   if pretrained else None)
        model = models.mobilenet_v3_large(weights=weights)
    elif size == "small":
        weights = (models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
                   if pretrained else None)
        model = models.mobilenet_v3_small(weights=weights)
    else:
        raise ValueError(f"size must be 'large' or 'small', got {size!r}")

    if freeze_backbone:
        for p in model.parameters():
            p.requires_grad = False
        # Re-enable the classifier we'll attach
        # (parameters of the new head start requires_grad=True automatically)

    # Replace the final 1000-way classifier with our binary head.
    # MobileNetV3 classifier is Sequential([Linear, Hardswish, Dropout, Linear])
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, 1)

    return model

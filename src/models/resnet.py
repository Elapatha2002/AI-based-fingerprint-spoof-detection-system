"""
ResNet50 (V2 variant) backbone with a binary classification head.

We use torchvision's ResNet50 with ImageNet-pretrained weights, then
replace the final FC with a single-logit head. Output is the *logit*
for class=spoof (use BCEWithLogitsLoss).

This is the proposal's primary backbone (§4.5). CBAM attention will be
added in Phase 3.
"""
import torch
import torch.nn as nn
from torchvision import models


def build_resnet50(pretrained: bool = True, freeze_backbone: bool = False) -> nn.Module:
    """
    Returns a ResNet50 with a single-logit binary head.

    Args:
        pretrained: load ImageNet weights (recommended for transfer learning).
        freeze_backbone: if True, only train the classifier head.
                         Useful for a fast first epoch sanity-check.
    """
    weights = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
    model = models.resnet50(weights=weights)

    if freeze_backbone:
        for p in model.parameters():
            p.requires_grad = False

    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 1),     # single logit -> sigmoid -> P(spoof)
    )
    return model


def count_parameters(model: nn.Module) -> tuple[int, int]:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable

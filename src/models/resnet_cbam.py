"""
ResNet50 with CBAM attention inserted into every Bottleneck block.

We do NOT rewrite ResNet from scratch. Instead, we take torchvision's
pretrained ResNet50 and wrap each Bottleneck so CBAM is applied to the
output of the 1x1 / 3x3 / 1x1 stack BEFORE the residual addition.

This keeps the pretrained weights of all conv layers intact — only the
new CBAM modules start untrained. They learn quickly because the rest of
the network already produces meaningful features.

Insertion point (per CBAM paper, Section 4.1):
    bottleneck:
        conv1 → bn1 → relu
        conv2 → bn2 → relu
        conv3 → bn3
        --> [CBAM here] <--
        + identity (downsample if needed)
        relu

Reference:
    Woo et al. 2018, "CBAM: Convolutional Block Attention Module."
"""
from __future__ import annotations

import torch.nn as nn
from torchvision import models

from src.models.cbam import CBAM


class CBAMBottleneck(nn.Module):
    """
    Wraps a torchvision.models.resnet.Bottleneck and applies CBAM
    to the post-bn3 feature map before residual addition.
    """

    def __init__(self, bottleneck: nn.Module, reduction: int = 16,
                 spatial_kernel: int = 7):
        super().__init__()
        # Keep the original bottleneck's layers
        self.conv1 = bottleneck.conv1
        self.bn1 = bottleneck.bn1
        self.conv2 = bottleneck.conv2
        self.bn2 = bottleneck.bn2
        self.conv3 = bottleneck.conv3
        self.bn3 = bottleneck.bn3
        self.relu = bottleneck.relu
        self.downsample = bottleneck.downsample
        self.stride = bottleneck.stride

        # CBAM operates on the bottleneck's output channels (= bn3 channels)
        out_channels = self.bn3.num_features
        self.cbam = CBAM(out_channels, reduction=reduction,
                         spatial_kernel=spatial_kernel)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        # CBAM gate — channel attention then spatial attention
        out = self.cbam(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out = out + identity
        out = self.relu(out)
        return out


def build_resnet50_cbam(pretrained: bool = True,
                        freeze_backbone: bool = False,
                        reduction: int = 16,
                        spatial_kernel: int = 7) -> nn.Module:
    """
    Build a ResNet50 with CBAM in every Bottleneck and a single-logit
    binary head.

    Args:
        pretrained:      load ImageNet ResNet50 weights for the conv layers
        freeze_backbone: freeze everything except CBAM modules and the head
                         (useful for a fast first epoch warm-up)
        reduction:       CBAM channel-attention reduction ratio
        spatial_kernel:  CBAM spatial-attention kernel (3 or 7)
    """
    weights = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
    model = models.resnet50(weights=weights)

    # Replace each Bottleneck with a CBAM-wrapped version
    for layer_name in ("layer1", "layer2", "layer3", "layer4"):
        layer = getattr(model, layer_name)
        new_blocks = []
        for block in layer:
            new_blocks.append(
                CBAMBottleneck(block, reduction=reduction,
                               spatial_kernel=spatial_kernel)
            )
        setattr(model, layer_name, nn.Sequential(*new_blocks))

    # Optional freeze (CBAM + classifier stays trainable)
    if freeze_backbone:
        for name, p in model.named_parameters():
            if "cbam" in name or name.startswith("fc"):
                p.requires_grad = True
            else:
                p.requires_grad = False

    # Replace classifier head
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 1),
    )
    return model

"""
ResNet50 with FSD-CBAM inserted at layer3 and layer4 only.

Design decisions (see fsd_cbam.py for full rationale):

  • FSD-CBAM is inserted only in the deeper semantic layers. layer3's
    Bottlenecks operate on 14×14 feature maps and receive a wide 11×11
    spatial kernel; layer4 operates on 7×7 feature maps and receives a 7×7
    kernel to fit the input.

  • layer1 and layer2 remain unchanged. Their features are generic
    (edge- and blob-response levels) and gating them provides marginal
    domain benefit at the cost of distorting the ImageNet pretraining signal.

  • The classifier head is replaced with a single-logit binary head
    identical in shape to the head used elsewhere in the project so that
    downstream code (training loop, XAI wrappers, Streamlit service) does
    not require modification.

Total added parameters relative to baseline ResNet50:
    ~1.5M (approximate; three MLPs per Bottleneck at reduction ratios
    8/16/32, only in layer3 (6 blocks) and layer4 (3 blocks)).
"""
from __future__ import annotations

import torch.nn as nn
from torchvision import models

from src.models.fsd_cbam import FSDCBAM


# Feature-map size and appropriate spatial-attention kernel per layer.
# Format: layer_name -> (feature_map_size, spatial_kernel_size)
LAYER_SPEC = {
    "layer1": (56, 7),
    "layer2": (28, 7),
    "layer3": (14, 7),
    "layer4": (7,  7),
}


class FSDCBAMBottleneck(nn.Module):
    """Wraps a torchvision.models.resnet.Bottleneck and applies FSD-CBAM
    to the post-bn3 feature map before residual addition."""

    def __init__(self, bottleneck: nn.Module,
                 reduction_ratios: tuple[int, ...] = (8, 16),
                 spatial_kernel: int = 7):
        super().__init__()
        self.conv1 = bottleneck.conv1
        self.bn1 = bottleneck.bn1
        self.conv2 = bottleneck.conv2
        self.bn2 = bottleneck.bn2
        self.conv3 = bottleneck.conv3
        self.bn3 = bottleneck.bn3
        self.relu = bottleneck.relu
        self.downsample = bottleneck.downsample
        self.stride = bottleneck.stride

        out_channels = self.bn3.num_features
        self.fsd_cbam = FSDCBAM(
            channels=out_channels,
            reduction_ratios=reduction_ratios,
            spatial_kernel=spatial_kernel,
        )

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

        # FSD-CBAM gate — multi-scale channel then wide spatial
        out = self.fsd_cbam(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out = out + identity
        out = self.relu(out)
        return out


def build_resnet50_fsd_cbam(pretrained: bool = True,
                            freeze_backbone: bool = False,
                            layers: tuple[int, ...] = (3, 4),
                            reduction_ratios: tuple[int, ...] = (8, 16)
                           ) -> nn.Module:
    """Build a ResNet50 with FSD-CBAM at the specified layers.

    Args:
        pretrained:       load ImageNet weights for the conv trunk
        freeze_backbone:  freeze everything except FSD-CBAM modules and
                          the classifier head
        layers:           which layers to insert FSD-CBAM into
                          (default: layer3 and layer4)
        reduction_ratios: channel-attention reduction ratios per Bottleneck
    """
    if not all(1 <= l <= 4 for l in layers):
        raise ValueError(f"layers must be a subset of (1,2,3,4), got {layers}")

    weights = models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
    model = models.resnet50(weights=weights)

    for lvl in layers:
        name = f"layer{lvl}"
        _, kernel = LAYER_SPEC[name]
        layer = getattr(model, name)
        new_blocks = []
        for block in layer:
            new_blocks.append(FSDCBAMBottleneck(
                block,
                reduction_ratios=reduction_ratios,
                spatial_kernel=kernel,
            ))
        setattr(model, name, nn.Sequential(*new_blocks))

    if freeze_backbone:
        for name, p in model.named_parameters():
            if "fsd_cbam" in name or name.startswith("fc"):
                p.requires_grad = True
            else:
                p.requires_grad = False

    # Replace classifier head with single-logit binary head
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 1),
    )

    return model

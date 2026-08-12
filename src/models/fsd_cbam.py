"""
FSD-CBAM — Fingerprint Spoof Detection Convolutional Block Attention Module.

An attention module tailored to fingerprint spoof detection, derived from
CBAM (Woo et al., 2018) with three domain-specific modifications:

  1. Multi-Scale Channel Attention
     Standard CBAM uses a single MLP with reduction ratio r = 16. Fingerprint
     texture varies across multiple scales: fine pore-perspiration detail,
     mid-scale ridge sharpness, and coarse ridge orientation. A single
     reduction ratio biases the channel gate toward one scale. FSD-CBAM uses
     three parallel MLPs at reduction ratios r ∈ {8, 16, 32}, whose sigmoid
     outputs are averaged. This lets the gate simultaneously respond to
     features at multiple channel-abstraction levels.

  2. Wide Spatial Attention
     Standard CBAM uses a 7×7 spatial kernel. Fingerprint ridges span
     approximately 30-50 pixels at 500 DPI (roughly 3-5 pixels in ResNet50's
     layer3 14×14 feature map, but a full ridge-orientation neighbourhood
     spans much more). Widening the spatial kernel to 11×11 at layer3
     captures a larger portion of the ridge-context field. At layer4 the
     feature map is 7×7, so the kernel is capped at 7 to fit the input.

  3. Selective Insertion (in resnet_fsd_cbam.py)
     Standard CBAM is inserted after every Bottleneck. FSD-CBAM is inserted
     only in the deeper semantic layers (layer3 and layer4). Rationale:
     low-level layers (layer1, layer2) capture generic edge and blob
     responses shared by all natural images; attention gating them adds
     parameters without domain relevance and risks distorting the ImageNet
     pretraining signal. Deeper layers encode class-discriminative
     representations where texture-aware gating pays off.

References:
    Woo, S., Park, J., Lee, J.-Y., & Kweon, I. S. (2018). CBAM:
    Convolutional Block Attention Module. ECCV.
"""
import torch
import torch.nn as nn


class MultiScaleChannelAttention(nn.Module):
    """Channel attention with several parallel MLPs at different reduction ratios.

    Args:
        channels:          number of channels in the input feature map
        reduction_ratios:  tuple of reduction ratios for the parallel MLPs.
                           Default (8, 16, 32) — captures fine, medium and
                           coarse channel abstractions.
    """

    def __init__(self, channels: int,
                 reduction_ratios: tuple[int, ...] = (8, 16)):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)

        self.mlps = nn.ModuleList([
            nn.Sequential(
                nn.Linear(channels, max(channels // r, 1), bias=False),
                nn.ReLU(inplace=False),
                nn.Linear(max(channels // r, 1), channels, bias=False),
            )
            for r in reduction_ratios
        ])

        self.n_scales = len(reduction_ratios)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        avg = self.avg_pool(x).view(b, c)
        mx = self.max_pool(x).view(b, c)

        # Sum contributions from every scale's MLP applied to both pooled vectors,
        # then average across scales for a scale-normalised gate.
        acc = torch.zeros(b, c, device=x.device, dtype=x.dtype)
        for mlp in self.mlps:
            acc = acc + mlp(avg) + mlp(mx)
        gate = torch.sigmoid(acc / self.n_scales)
        return x * gate.view(b, c, 1, 1)


class WideSpatialAttention(nn.Module):
    """Spatial attention with a configurable (typically wider) kernel.

    Args:
        kernel_size:  odd integer. Default 11 for layer3 feature maps;
                      caller should pass 7 for layer4's 7×7 feature maps.
    """

    def __init__(self, kernel_size: int = 11):
        super().__init__()
        if kernel_size % 2 == 0:
            raise ValueError(f"kernel_size must be odd, got {kernel_size}")
        self.conv = nn.Conv2d(
            in_channels=2,
            out_channels=1,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            bias=False,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = torch.mean(x, dim=1, keepdim=True)           # (B, 1, H, W)
        mx, _ = torch.max(x, dim=1, keepdim=True)          # (B, 1, H, W)
        cat = torch.cat([avg, mx], dim=1)                  # (B, 2, H, W)
        gate = torch.sigmoid(self.conv(cat))               # (B, 1, H, W)
        return x * gate


class FSDCBAM(nn.Module):
    """FSD-CBAM = Multi-Scale Channel Attention → Wide Spatial Attention.

    Args:
        channels:          number of channels in the input feature map
        reduction_ratios:  channel-attention reduction ratios
        spatial_kernel:    spatial-attention kernel size (must be odd)
    """

    def __init__(self, channels: int,
                 reduction_ratios: tuple[int, ...] = (8, 16),
                 spatial_kernel: int = 7):
        super().__init__()
        self.channel = MultiScaleChannelAttention(channels, reduction_ratios)
        self.spatial = WideSpatialAttention(spatial_kernel)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.channel(x)
        x = self.spatial(x)
        return x

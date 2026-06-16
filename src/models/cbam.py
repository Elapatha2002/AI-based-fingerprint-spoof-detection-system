"""
CBAM — Convolutional Block Attention Module.

Reference: Woo et al. (2018), "CBAM: Convolutional Block Attention Module."
ECCV. arXiv:1807.06521

Architecture:
    input  ─► Channel Attention ─► Spatial Attention ─► output

Each attention module produces a multiplicative gate. Channel attention
re-weights feature channels; spatial attention re-weights pixel locations.

Designed to drop into any conv backbone. We attach it inside every
Bottleneck of ResNet50 (see resnet_cbam.py).
"""
import torch
import torch.nn as nn


class ChannelAttention(nn.Module):
    """
    Two parallel pools (avg + max) → shared 2-layer MLP → sigmoid gate.

    Args:
        channels:  number of channels in the feature map
        reduction: channels are bottlenecked to channels/reduction inside MLP
    """

    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        hidden = max(channels // reduction, 1)

        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)

        # Shared MLP across both pooled vectors (paper §3.1)
        self.mlp = nn.Sequential(
            nn.Linear(channels, hidden, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, channels, bias=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.shape
        avg = self.mlp(self.avg_pool(x).view(b, c))
        mx = self.mlp(self.max_pool(x).view(b, c))
        attn = torch.sigmoid(avg + mx).view(b, c, 1, 1)
        return x * attn


class SpatialAttention(nn.Module):
    """
    Channel-wise avg + max → 2-channel map → 7x7 conv → sigmoid gate.
    """

    def __init__(self, kernel_size: int = 7):
        super().__init__()
        assert kernel_size in (3, 7), "CBAM paper uses 3 or 7"
        self.conv = nn.Conv2d(
            in_channels=2,
            out_channels=1,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            bias=False,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = torch.mean(x, dim=1, keepdim=True)            # (B, 1, H, W)
        mx, _ = torch.max(x, dim=1, keepdim=True)           # (B, 1, H, W)
        cat = torch.cat([avg, mx], dim=1)                   # (B, 2, H, W)
        attn = torch.sigmoid(self.conv(cat))                # (B, 1, H, W)
        return x * attn


class CBAM(nn.Module):
    """
    Channel attention applied first, then spatial attention.
    Returns the same shape as input.
    """

    def __init__(self, channels: int, reduction: int = 16,
                 spatial_kernel: int = 7):
        super().__init__()
        self.channel = ChannelAttention(channels, reduction)
        self.spatial = SpatialAttention(spatial_kernel)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.channel(x)
        x = self.spatial(x)
        return x

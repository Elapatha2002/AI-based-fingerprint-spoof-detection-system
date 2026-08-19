"""
Unified model factory.

Single entry point so the training script doesn't need to know
which file each backbone lives in.

Adding a new backbone: implement `build_<name>(pretrained, freeze_backbone)`
in its own file, then register it in MODEL_REGISTRY below.
"""
from __future__ import annotations

import torch.nn as nn

from src.models.resnet import build_resnet50
from src.models.resnet_cbam import build_resnet50_cbam
from src.models.resnet_fsd_cbam import build_resnet50_fsd_cbam
from src.models.mobilenet import build_mobilenetv3
from src.models.mobilenet_fsd_cbam import build_mobilenetv3_fsd_cbam


def _resnet50(**kw):
    return build_resnet50(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
    )


def _resnet50_cbam(**kw):
    return build_resnet50_cbam(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
        reduction=kw.get("reduction", 16),
        spatial_kernel=kw.get("spatial_kernel", 7),
    )


def _fsd_cbam(**kw):
    return build_resnet50_fsd_cbam(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
        layers=kw.get("layers", (3, 4)),
        reduction_ratios=kw.get("reduction_ratios", (8, 16)),
    )


def _mobilenetv3_large(**kw):
    return build_mobilenetv3(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
        size="large",
    )


def _mobilenet_fsd_cbam(**kw):
    return build_mobilenetv3_fsd_cbam(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
        reduction_ratios=kw.get("reduction_ratios", (8, 16)),
    )


def _mobilenetv3_small(**kw):
    return build_mobilenetv3(
        pretrained=kw.get("pretrained", True),
        freeze_backbone=kw.get("freeze_backbone", False),
        size="small",
    )


MODEL_REGISTRY = {
    "resnet50": _resnet50,
    "resnet50_cbam": _resnet50_cbam,
    "fsd_cbam": _fsd_cbam,
    "mobilenet_fsd_cbam": _mobilenet_fsd_cbam,
    "mobilenetv3_large": _mobilenetv3_large,
    "mobilenetv3_small": _mobilenetv3_small,
}


def get_model(name: str, **kw) -> nn.Module:
    """Return a model by registry name. Raises if name is unknown."""
    if name not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model '{name}'. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[name](**kw)


def count_parameters(model: nn.Module) -> tuple[int, int]:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable

"""Lightweight model/checkpoint configuration without importing PyTorch."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT = (PROJECT_ROOT / "checkpoints" /
                      "mobilenetv3_large_20260616_105902" / "best.pth")
DEFAULT_MODEL_NAME = "mobilenetv3_large"
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def resolve_checkpoint(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def configured_selection(session_state: Mapping | None = None) -> tuple[str, Path]:
    state = session_state if session_state is not None else {}
    model_name = (state.get("selected_model") or
                  os.environ.get("FSDXAI_MODEL", DEFAULT_MODEL_NAME))
    checkpoint = (state.get("selected_checkpoint") or
                  os.environ.get("FSDXAI_CHECKPOINT", str(DEFAULT_CHECKPOINT)))
    return str(model_name), resolve_checkpoint(checkpoint)


def checkpoint_state(path: Path) -> tuple[str, str]:
    """Return a machine state and short user-facing description."""
    if not path.is_file():
        return "missing", "checkpoint missing"
    try:
        with path.open("rb") as stream:
            prefix = stream.read(len(LFS_POINTER_PREFIX))
    except OSError:
        return "unreadable", "checkpoint unreadable"
    if prefix == LFS_POINTER_PREFIX:
        return "lfs_pointer", "model data not downloaded"
    return "ready", "ready on demand"


def require_materialized_checkpoint(path: Path) -> None:
    state, _ = checkpoint_state(path)
    if state == "ready":
        return
    if state == "lfs_pointer":
        raise RuntimeError(
            "Checkpoint is a Git LFS pointer, not model data. Run "
            "'git lfs install' and 'git lfs pull', then restart the application."
        )
    if state == "missing":
        raise FileNotFoundError(
            f"Checkpoint not found: {path}. Set FSDXAI_CHECKPOINT to a valid path."
        )
    raise RuntimeError(f"Checkpoint cannot be read: {path}")


def architecture_for_folder(name: str) -> str | None:
    if name.startswith("mobilenet_fsd_cbam"):
        return "mobilenet_fsd_cbam"
    if name.startswith("fsd_cbam_v2_20260810_122231"):
        return "fsd_cbam"
    if name.startswith("resnet50_cbam"):
        return "resnet50_cbam"
    if name.startswith("resnet50"):
        return "resnet50"
    if name.startswith("mobilenetv3_large"):
        return "mobilenetv3_large"
    if name.startswith("mobilenetv3_small"):
        return "mobilenetv3_small"
    return None


def list_available_checkpoints() -> list[dict]:
    root = PROJECT_ROOT / "checkpoints"
    if not root.exists():
        return []
    found = []
    for directory in sorted(root.iterdir()):
        best = directory / "best.pth"
        if not directory.is_dir() or not best.exists():
            continue
        architecture = architecture_for_folder(directory.name)
        if architecture:
            state, state_label = checkpoint_state(best)
            found.append({
                "folder": directory.name,
                "arch": architecture,
                "path": str(best),
                "state": state,
                "state_label": state_label,
            })
    return found

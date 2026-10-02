"""Load the versioned, private background distribution used by SHAP.

The background images live in the configured evidence bucket rather than in
the public application repository.  A small JSON manifest fixes their order,
labels and SHA-256 digests so every explanation uses the same reference set.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from typing import Any

from PIL import Image
import torch

from src.data.transforms import eval_transform


DEFAULT_PREFIX = "shap-background/v1"
EXPECTED_VERSION = 1
_CACHE: dict[tuple[str, int], tuple[torch.Tensor, dict[str, Any]]] = {}


class ShapBackgroundError(RuntimeError):
    """The fixed SHAP reference distribution cannot be used safely."""


def configured_prefix() -> str:
    prefix = os.environ.get("FSDXAI_SHAP_BACKGROUND_PREFIX", DEFAULT_PREFIX)
    prefix = prefix.strip().strip("/")
    if not prefix or ".." in prefix.split("/"):
        raise ShapBackgroundError("FSDXAI_SHAP_BACKGROUND_PREFIX is invalid.")
    return prefix


def _validated_manifest(raw: bytes, prefix: str, n: int) -> dict[str, Any]:
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShapBackgroundError("The SHAP background manifest is not valid JSON.") from exc

    if manifest.get("schema_version") != EXPECTED_VERSION:
        raise ShapBackgroundError("The SHAP background manifest version is unsupported.")
    if manifest.get("prefix") != prefix:
        raise ShapBackgroundError("The SHAP background manifest prefix does not match its location.")

    entries = manifest.get("images")
    if not isinstance(entries, list) or len(entries) < n:
        raise ShapBackgroundError(
            f"The fixed SHAP background requires {n} images; "
            f"the manifest contains {len(entries) if isinstance(entries, list) else 0}."
        )
    selected = entries[:n]
    labels = [entry.get("label") for entry in selected if isinstance(entry, dict)]
    if labels.count("live") != n // 2 or labels.count("spoof") != n - (n // 2):
        raise ShapBackgroundError(
            "The fixed SHAP background is not balanced between live and spoof samples."
        )
    return manifest


def load_fixed_background(
    n: int = 8,
    *,
    storage_service=None,
    prefix: str | None = None,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Download, verify and preprocess the fixed background distribution.

    The default service is the application's configured private storage.  An
    injectable service keeps integrity validation directly unit-testable.
    """
    if n <= 0 or n % 2:
        raise ShapBackgroundError("The SHAP background size must be a positive even number.")
    prefix = (prefix or configured_prefix()).strip("/")
    cache_key = (prefix, n)
    if storage_service is None and cache_key in _CACHE:
        return _CACHE[cache_key]

    if storage_service is None:
        from app.services.storage import get_storage
        storage_service = get_storage()

    manifest_key = f"{prefix}/manifest.json"
    try:
        manifest = _validated_manifest(
            storage_service.download_bytes(manifest_key), prefix, n
        )
    except ShapBackgroundError:
        raise
    except Exception as exc:
        raise ShapBackgroundError(
            f"The fixed SHAP background is unavailable at {manifest_key}. "
            "Run tools/prepare_shap_background.py with the deployment's "
            "private storage configuration."
        ) from exc

    transform = eval_transform()
    tensors = []
    for entry in manifest["images"][:n]:
        if not isinstance(entry, dict):
            raise ShapBackgroundError("The SHAP background manifest contains an invalid entry.")
        key = str(entry.get("object_key", ""))
        expected_hash = str(entry.get("sha256", ""))
        if not key.startswith(f"{prefix}/") or len(expected_hash) != 64:
            raise ShapBackgroundError("A SHAP background manifest entry is incomplete.")
        try:
            image_bytes = storage_service.download_bytes(key)
        except Exception as exc:
            raise ShapBackgroundError(f"SHAP background object is unavailable: {key}") from exc
        actual_hash = hashlib.sha256(image_bytes).hexdigest()
        if actual_hash != expected_hash:
            raise ShapBackgroundError(
                f"SHAP background integrity check failed for {key}."
            )
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                tensors.append(transform(image.convert("RGB")))
        except Exception as exc:
            raise ShapBackgroundError(f"SHAP background image is invalid: {key}") from exc

    result = (torch.stack(tensors), manifest)
    if storage_service.__class__.__module__ == "app.services.storage":
        _CACHE[cache_key] = result
    return result


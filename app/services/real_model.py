"""
Real model service for the Streamlit app.

Exposes the SAME public API as `mock_model.py` (predict / explain /
placeholder_image) so the views need no changes. The dispatcher in
mock_model.py routes calls here when the environment variable
`FSDXAI_REAL_MODEL=1` is set.

Configure which checkpoint to load via env vars (read once at first use):
    FSDXAI_CHECKPOINT   path to best.pth (relative to project root or absolute)
    FSDXAI_MODEL        one of: resnet50 | resnet50_cbam |
                                mobilenetv3_large | mobilenetv3_small

Defaults:
    FSDXAI_CHECKPOINT   <project_root>/checkpoints/mobilenetv3_large_20260616_105902/best.pth
    FSDXAI_MODEL        mobilenetv3_large

Why MobileNetV3-Large as default: 4× faster XAI on CPU than ResNet50,
and faithfulness metrics show it's a strong choice (see thesis §4.5).
"""
from __future__ import annotations

import io
import gc
import re
import sys
import time
from pathlib import Path

import hashlib
import numpy as np
import streamlit as st
import torch
from PIL import Image

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.services.model_config import (
    DEFAULT_CHECKPOINT, DEFAULT_MODEL_NAME, configured_selection,
    list_available_checkpoints, require_materialized_checkpoint,
)


# Make `src.*` importable when Streamlit runs `streamlit_app.py`
APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────────────────
# One-time model load
# ─────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading real model …")
def _load_model(model_name: str, ckpt_str: str) -> dict:
    """Cache key includes (model_name, ckpt_str) — each combination is cached
    separately, so switching models in the UI doesn't reload already-seen ones."""
    ckpt_path = Path(ckpt_str)
    if not ckpt_path.is_absolute():
        ckpt_path = PROJECT_ROOT / ckpt_path
    # Fail before allocating a neural network when a clone contains only the
    # small Git LFS pointer. This replaces PyTorch's cryptic "invalid load key v".
    require_materialized_checkpoint(ckpt_path)

    from src.models.factory import get_model, MODEL_REGISTRY
    from src.xai.base import disable_inplace_ops, clear_all_hooks

    if model_name not in MODEL_REGISTRY:
        raise RuntimeError(
            f"Unknown model architecture: {model_name!r}. "
            f"Allowed: {list(MODEL_REGISTRY.keys())}"
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = get_model(model_name, pretrained=False).to(device)

    state = torch.load(ckpt_path, map_location=device, weights_only=False)
    if isinstance(state, dict) and "model_state" in state:
        model.load_state_dict(state["model_state"])
    else:
        model.load_state_dict(state)

    model.eval()
    disable_inplace_ops(model)
    clear_all_hooks(model)

    short = ckpt_path.parent.name
    with ckpt_path.open("rb") as checkpoint_file:
        checkpoint_sha256 = hashlib.file_digest(checkpoint_file, "sha256").hexdigest()

    return {
        "model": model,
        "device": device,
        "name": model_name,
        "checkpoint_path": str(ckpt_path),
        "checkpoint_short": short,
        "checkpoint_sha256": checkpoint_sha256,
        "commit": short[-8:] if len(short) >= 8 else short,
    }


def get_service_info() -> dict:
    """Resolve which checkpoint to load (session state > env var > default)
    and return its cached service info."""
    model_name, checkpoint = configured_selection(st.session_state)
    return _load_model(model_name, str(checkpoint))


# ─────────────────────────────────────────────────────────────────────────
# Public API — matches mock_model.predict / explain / placeholder_image
# ─────────────────────────────────────────────────────────────────────────

def predict(filename: str, image: Image.Image | None = None) -> dict:
    """Run the trained classifier. Same return shape as mock_model.predict()."""
    from src.xai.base import preprocess

    svc = get_service_info()
    model = svc["model"]
    device = svc["device"]

    if image is None:
        image = placeholder_image(filename)
    if image.mode != "RGB":
        image = image.convert("RGB")

    t0 = time.time()
    tensor = preprocess(image).to(device)
    t1 = time.time()
    with torch.inference_mode():
        logit = model(tensor).item()
    t2 = time.time()

    p_spoof = 1.0 / (1.0 + np.exp(-logit))
    label = "spoof" if p_spoof >= 0.5 else "live"
    confidence = p_spoof if label == "spoof" else 1.0 - p_spoof
    borderline = abs(p_spoof - 0.5) < 0.1

    material = _parse_material_from_filename(filename) if label == "spoof" else None

    return {
        "filename": filename,
        "label": label,
        "confidence": confidence,
        "raw_score": p_spoof,
        "threshold_used": 0.5,
        "borderline": borderline,
        "material": material,
        "material_confidence": 0.80 if material else None,
        # NFIQ2 + anomaly are not implemented in this phase — placeholders so the
        # UI renders. Marked clearly in the README as "not real."
        "nfiq2": 70,
        "quality_tier": "medium",
        "anomaly_score": 0.18,
        "known_pattern": True,
        "vae_recon_error": 0.027,
        "timing_ms": {
            "preprocess": int((t1 - t0) * 1000),
            "inference": int((t2 - t1) * 1000),
            "total": int((t2 - t0) * 1000),
        },
        "model": {
            "name": svc["name"],
            "version": "real",
            "commit": svc["commit"],
            "checkpoint_short": svc["checkpoint_short"],
            "checkpoint_sha256": svc["checkpoint_sha256"],
        },
    }


def explain_one(method: str, filename: str,
                image: Image.Image | None = None) -> dict:
    """Run one XAI method and return its panel.

    Hosted deployments call this method directly so SHAP, LIME and
    Grad-CAM++ never occupy the same request.  Apart from improving the user
    feedback, this bounds peak memory on small Streamlit Cloud containers.
    """
    method = method.lower().strip()
    if method not in {"gradcam", "shap", "lime"}:
        raise ValueError(f"Unknown XAI method: {method!r}")

    svc = get_service_info()
    model = svc["model"]
    device = svc["device"]
    model_name = svc["name"]

    if image is None:
        image = placeholder_image(filename)
    if image.mode != "RGB":
        image = image.convert("RGB")

    try:
        if method == "gradcam":
            from src.xai import gradcam
            result = gradcam.explain(model, image, model_name, device)
            return _panel_from_result(result, faith=0.78, iou=0.71)
        if method == "shap":
            from src.xai import shap_explainer
            result = shap_explainer.explain(
                model, image, model_name, device, background_n=8,
            )
            return _panel_from_result(result, faith=0.81, iou=0.65)

        from src.xai import lime_explainer
        result = lime_explainer.explain(
            model, image, model_name, device, num_samples=300,
        )
        return _panel_from_result(result, faith=0.69, iou=0.58)
    except Exception as exc:
        pretty = {"gradcam": "Grad-CAM++", "shap": "SHAP", "lime": "LIME"}
        return _fallback_panel(pretty[method], str(exc))
    finally:
        # Explanation libraries create hooks, graphs and temporary arrays.  Do
        # not retain them between independent Streamlit requests.
        try:
            from src.xai.base import clear_all_hooks
            clear_all_hooks(model)
        except Exception:
            pass
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def explain(filename: str, image: Image.Image | None = None) -> dict:
    """Run all XAI methods for CLI/tests; hosted UI uses ``explain_one``."""
    panels: dict = {}
    for method in ("gradcam", "shap", "lime"):
        panels[method] = explain_one(method, filename, image)

    return panels


def placeholder_image(filename: str = "placeholder") -> Image.Image:
    """Generate a procedural fingerprint-like image. Used when no image is supplied
    (e.g. after re-opening a History entry that didn't keep bytes)."""
    seed = int(hashlib.md5(filename.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    h, w = 480, 480
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2 + rng.integers(-30, 30), w / 2 + rng.integers(-30, 30)
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    theta = np.arctan2(yy - cy, xx - cx)
    pattern = np.sin(r * 0.25 + theta * 4) * 0.5 + 0.5
    noise = rng.normal(0, 0.08, (h, w))
    img = np.clip(pattern * 0.85 + 0.1 + noise, 0, 1)
    img = (img * 255).astype(np.uint8)
    return Image.fromarray(img).convert("RGB")


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

_MATERIAL_PATTERN = re.compile(
    r"_(Silicone|Gelatin|Latex|Playdoh|Ecoflex|WoodGlue|BodyDouble|"
    r"LiquidEcoflex|Modasil|OOMOO|Silgum|RTV|Persona|Scan)",
    re.IGNORECASE,
)


def _parse_material_from_filename(filename: str) -> str | None:
    """Best-effort spoof material extraction from LivDet-style filenames."""
    m = _MATERIAL_PATTERN.search(filename)
    if not m:
        return None
    raw = m.group(1)
    canonical = {
        "silicone": "Silicone", "gelatin": "Gelatin", "latex": "Latex",
        "playdoh": "Playdoh", "ecoflex": "Ecoflex", "woodglue": "WoodGlue",
        "bodydouble": "BodyDouble", "liquidecoflex": "LiquidEcoflex",
        "modasil": "Modasil", "oomoo": "OOMOO", "silgum": "Silgum",
        "rtv": "RTV", "persona": "Persona", "scan": "Scan",
    }
    return canonical.get(raw.lower(), raw)


def _panel_from_result(result, faith: float, iou: float) -> dict:
    """Format an XAIResult into the dict shape expected by the views.

    `faith` and `iou` are reference values from the thesis faithfulness study —
    they're shown in the UI as illustrative metrics, not per-image scores
    (per-image faithfulness would require 20 extra forward passes per call).
    """
    return {
        "image": result.overlay_png,
        "faithfulness": faith,
        "localization_iou": iou,
        "compute_ms": result.compute_ms,
        "summary": result.summary,
    }


def _fallback_panel(method_name: str, err: str) -> dict:
    """Render a clean error tile so the UI doesn't break if one XAI fails."""
    fig, ax = plt.subplots(figsize=(3.0, 3.0), dpi=120)
    ax.text(0.5, 0.55, f"{method_name}",
            ha="center", va="center", color="white", fontsize=14,
            fontweight="bold")
    ax.text(0.5, 0.35, "failed",
            ha="center", va="center", color="#F85149", fontsize=11)
    ax.text(0.5, 0.20, err[:60] + ("…" if len(err) > 60 else ""),
            ha="center", va="center", color="#8B949E", fontsize=8)
    ax.axis("off")
    fig.patch.set_facecolor("#0B0F14")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#0B0F14",
                bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return {
        "status": "error",
        "error": err,
        "image": buf.getvalue(),
        "faithfulness": 0.0,
        "localization_iou": 0.0,
        "compute_ms": 0,
        "summary": f"{method_name} failed: {err[:80]}",
    }

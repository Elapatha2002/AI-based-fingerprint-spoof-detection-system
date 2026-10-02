"""
Mock predictor + mock XAI generator.

By default produces deterministic outputs based on filename hash, so the
prototype works without any trained model. Set the environment variable
`FSDXAI_REAL_MODEL=1` BEFORE launching Streamlit to dispatch every call
to the real-model service in `real_model.py` instead.

The dispatcher pattern keeps views unchanged whether you're in mock or
real mode.
"""
import hashlib
import io
import os
import time
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SPOOF_MATERIALS = ["Silicone", "Gelatin", "Latex", "Play-Doh", "Wood Glue", "Ecoflex"]


def _real_mode() -> bool:
    """Return True if the user has opted into real model + XAI inference."""
    return os.environ.get("FSDXAI_REAL_MODEL") == "1"


def _seed_from_name(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


def predict(filename: str, image: Image.Image | None = None) -> dict:
    """Return a fake but deterministic prediction. Mimics latency of real model.

    If FSDXAI_REAL_MODEL=1 is set, dispatches to real_model.predict() instead.
    """
    if _real_mode():
        from services import real_model
        return real_model.predict(filename, image)

    rng = np.random.default_rng(_seed_from_name(filename))

    # Filename hints — useful when iterating against a labelled dataset
    fname_lower = filename.lower()
    if any(s in fname_lower for s in ["spoof", "fake", "silic", "gelat", "latex", "playdoh", "ecoflex", "glue"]):
        prob_spoof = float(rng.uniform(0.78, 0.98))
    elif "live" in fname_lower or "real" in fname_lower or "bona" in fname_lower:
        prob_spoof = float(rng.uniform(0.02, 0.22))
    else:
        prob_spoof = float(rng.uniform(0.0, 1.0))

    label = "spoof" if prob_spoof > 0.5 else "live"
    confidence = prob_spoof if label == "spoof" else 1.0 - prob_spoof
    is_borderline = abs(prob_spoof - 0.5) < 0.1

    nfiq2 = int(rng.integers(35, 95))
    anomaly_score = float(rng.uniform(0.0, 0.45))
    known_pattern = anomaly_score < 0.35

    material = SPOOF_MATERIALS[int(rng.integers(0, len(SPOOF_MATERIALS)))] if label == "spoof" else None

    # Simulate latency
    time.sleep(0.05)

    return {
        "filename": filename,
        "label": label,
        "confidence": confidence,
        "raw_score": prob_spoof,
        "borderline": is_borderline,
        "material": material,
        "material_confidence": float(rng.uniform(0.55, 0.92)) if material else None,
        "nfiq2": nfiq2,
        "quality_tier": "high" if nfiq2 >= 60 else ("medium" if nfiq2 >= 30 else "low"),
        "anomaly_score": anomaly_score,
        "known_pattern": known_pattern,
        "vae_recon_error": float(rng.uniform(0.005, 0.08)),
        "timing_ms": {
            "preprocess": int(rng.integers(40, 70)),
            "inference": int(rng.integers(60, 110)),
            "total": int(rng.integers(120, 180)),
        },
        "model": {
            "name": "ResNet50V2-CBAM",
            "version": "v1.0.0-mock",
            "commit": "a3f9b21",
        },
    }


def _heatmap_image(base_img: Image.Image, seed: int, kind: str) -> bytes:
    """Generate a fake heatmap overlay PNG and return its bytes."""
    rng = np.random.default_rng(seed + ord(kind[0]))

    base = base_img.convert("RGB").resize((280, 280))
    base_arr = np.asarray(base)
    h, w = 280, 280

    # Fake attribution: gaussian blob centered around a random ridge area
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = rng.integers(80, 200), rng.integers(80, 200)
    sigma = 40 + rng.integers(0, 30)
    g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))

    if kind == "shap":
        # Add a second negative blob
        cy2, cx2 = rng.integers(50, 230), rng.integers(50, 230)
        g2 = np.exp(-((xx - cx2) ** 2 + (yy - cy2) ** 2) / (2 * sigma ** 2))
        attribution = g - 0.6 * g2
    elif kind == "lime":
        # Quantize into superpixels
        block = 28
        attribution = g
        attribution = (attribution.reshape(h // block, block, w // block, block)
                       .mean(axis=(1, 3)))
        attribution = np.kron(attribution, np.ones((block, block)))
    else:
        attribution = g

    attribution = attribution / (np.abs(attribution).max() + 1e-8)

    fig, ax = plt.subplots(figsize=(2.8, 2.8), dpi=100)
    ax.imshow(base_arr, alpha=0.55)
    cmap = "RdBu_r" if kind == "shap" else "viridis"
    ax.imshow(attribution, cmap=cmap, alpha=0.55, vmin=-1 if kind == "shap" else 0, vmax=1)
    ax.axis("off")
    fig.patch.set_facecolor("#0B0F14")
    ax.set_facecolor("#0B0F14")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0,
                facecolor="#0B0F14")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def explain(filename: str, image: Image.Image | None = None) -> dict:
    """Generate three XAI heatmaps + faithfulness scores. Slow (mimics SHAP/LIME).

    If FSDXAI_REAL_MODEL=1 is set, dispatches to real_model.explain() instead,
    which runs Grad-CAM++ / SHAP / LIME on the loaded trained model.
    """
    if _real_mode():
        from services import real_model
        return real_model.explain(filename, image)

    seed = _seed_from_name(filename)
    rng = np.random.default_rng(seed)

    if image is None:
        image = _generate_placeholder_fingerprint(seed)

    panels = {
        "gradcam": {
            "image": _heatmap_image(image, seed, "gradcam"),
            "faithfulness": round(float(rng.uniform(0.70, 0.85)), 3),
            "localization_iou": round(float(rng.uniform(0.65, 0.80)), 3),
            "compute_ms": 120,
            "summary": "Grad-CAM++ localized abnormal ridge continuity in the central region.",
        },
        "shap": {
            "image": _heatmap_image(image, seed, "shap"),
            "faithfulness": round(float(rng.uniform(0.72, 0.86)), 3),
            "localization_iou": round(float(rng.uniform(0.55, 0.75)), 3),
            "compute_ms": 3210,
            "summary": "SHAP attributed positive evidence to ridge texture, negative to background regions.",
        },
        "lime": {
            "image": _heatmap_image(image, seed, "lime"),
            "faithfulness": round(float(rng.uniform(0.55, 0.75)), 3),
            "localization_iou": round(float(rng.uniform(0.45, 0.65)), 3),
            "compute_ms": 5180,
            "summary": "LIME flagged 5 superpixels in the upper valley as decision-driving.",
        },
    }
    return panels


def explain_one(method: str, filename: str,
                image: Image.Image | None = None) -> dict:
    """Generate one explanation panel without running the other methods."""
    method = method.lower().strip()
    if method not in {"gradcam", "shap", "lime"}:
        raise ValueError(f"Unknown XAI method: {method!r}")
    if _real_mode():
        from services import real_model
        return real_model.explain_one(method, filename, image)

    seed = _seed_from_name(filename)
    rng = np.random.default_rng(seed)
    if image is None:
        image = _generate_placeholder_fingerprint(seed)

    configs = {
        "gradcam": (0.70, 0.85, 0.65, 0.80, 120,
                    "Grad-CAM++ localized abnormal ridge continuity in the central region."),
        "shap": (0.72, 0.86, 0.55, 0.75, 3210,
                 "SHAP attributed positive evidence to ridge texture, negative to background regions."),
        "lime": (0.55, 0.75, 0.45, 0.65, 5180,
                 "LIME flagged 5 superpixels in the upper valley as decision-driving."),
    }
    faith_low, faith_high, iou_low, iou_high, compute_ms, summary = configs[method]
    return {
        "image": _heatmap_image(image, seed, method),
        "faithfulness": round(float(rng.uniform(faith_low, faith_high)), 3),
        "localization_iou": round(float(rng.uniform(iou_low, iou_high)), 3),
        "compute_ms": compute_ms,
        "summary": summary,
    }


def _generate_placeholder_fingerprint(seed: int) -> Image.Image:
    """Generate a procedural fingerprint-like grayscale image."""
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


def placeholder_image(filename: str = "placeholder") -> Image.Image:
    """Public helper to build a placeholder fingerprint for the demo."""
    return _generate_placeholder_fingerprint(_seed_from_name(filename))

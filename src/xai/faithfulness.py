"""
Quantitative faithfulness metrics for XAI explanations.

Directly answers Research Question 2:
    "Which XAI technique most effectively highlights forensically relevant
     features?"

Four metric families implemented:

  1. Deletion-AUC  — progressively remove the most-attributed pixels and
                     measure how fast the model's confidence drops.
                     LOWER is better (faithful explanations cause the model
                     to lose confidence quickly when its evidence is taken away).

  2. Insertion-AUC — start from a blank baseline and progressively insert
                     the most-attributed pixels.
                     HIGHER is better (faithful explanations let the model
                     recover its prediction with very few pixels).

  3. Cross-method  — pairwise Pearson correlation + IoU at top-K% between
     correlation     pairs of XAI heatmaps. Measures agreement, not absolute
                     faithfulness.

  4. Stability     — variance across re-runs (LIME has stochastic
                     perturbations). Lower variance = more stable.

References:
    Petsiuk et al. (2018), "RISE: Randomized Input Sampling for Explanation"
    Samek et al. (2017), "Evaluating the Visualization of What a DNN Has Learned"
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from scipy.stats import pearsonr, spearmanr
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _target_prob(model: nn.Module, tensor: torch.Tensor,
                 target_class: int) -> float:
    """Probability of target_class for a single (1, 3, H, W) tensor."""
    with torch.inference_mode():
        logit = model(tensor).item()
    p_spoof = 1.0 / (1.0 + np.exp(-logit))
    return p_spoof if target_class == 1 else 1.0 - p_spoof


def _normalize_heatmap_size(heatmap: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    """Resize heatmap (H', W') to target (H, W) using bilinear interp."""
    if heatmap.shape == target_hw:
        return heatmap
    # PIL works in [0, 255]; preserve sign by scaling
    vmin, vmax = float(heatmap.min()), float(heatmap.max())
    if vmax - vmin < 1e-12:
        return np.zeros(target_hw, dtype=np.float32)
    normalized = (heatmap - vmin) / (vmax - vmin)
    img = Image.fromarray((normalized * 255).astype(np.uint8))
    img = img.resize((target_hw[1], target_hw[0]), Image.BILINEAR)
    resized = np.array(img).astype(np.float32) / 255.0
    return resized * (vmax - vmin) + vmin


def _rank_pixels_by_importance(heatmap: np.ndarray,
                                rng: np.random.Generator | None = None) -> np.ndarray:
    """
    Return pixel indices sorted by absolute importance (descending).
    Adds tiny noise to break ties — important for sparse heatmaps like LIME.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    flat = np.abs(heatmap).flatten()
    flat = flat + rng.uniform(0, 1e-9, size=flat.shape)
    return np.argsort(-flat)


# ─────────────────────────────────────────────────────────────────────────
# Deletion-AUC
# ─────────────────────────────────────────────────────────────────────────

def deletion_auc(model: nn.Module,
                 image_tensor: torch.Tensor,
                 heatmap: np.ndarray,
                 steps: int = 20,
                 device: torch.device | None = None) -> tuple[float, list[float]]:
    """
    Progressively replace the most-attributed pixels with the baseline
    (zero in normalized space = ImageNet mean image).

    Returns (auc, curve). Lower AUC = more faithful explanation.
    """
    if device is None:
        device = next(model.parameters()).device

    model.eval()
    image_tensor = image_tensor.to(device)
    H, W = image_tensor.shape[-2], image_tensor.shape[-1]
    heatmap = _normalize_heatmap_size(heatmap, (H, W))

    # Decide the target class based on the original prediction
    original = _target_prob(model, image_tensor, target_class=1)
    target_class = 1 if original >= 0.5 else 0

    sorted_idx = _rank_pixels_by_importance(heatmap)
    n_pixels = H * W
    pixels_per_step = max(1, n_pixels // steps)

    current = image_tensor.clone()
    curve: list[float] = [_target_prob(model, current, target_class)]

    for step in range(1, steps + 1):
        start = (step - 1) * pixels_per_step
        end = min(step * pixels_per_step, n_pixels)
        idx_slice = sorted_idx[start:end]
        ys, xs = np.divmod(idx_slice, W)
        current[0, :, ys, xs] = 0.0          # replace with baseline (mean image)
        curve.append(_target_prob(model, current, target_class))

    x = np.linspace(0, 1, len(curve))
    auc = float(np.trapezoid(curve, x))
    return auc, curve


# ─────────────────────────────────────────────────────────────────────────
# Insertion-AUC
# ─────────────────────────────────────────────────────────────────────────

def insertion_auc(model: nn.Module,
                  image_tensor: torch.Tensor,
                  heatmap: np.ndarray,
                  steps: int = 20,
                  device: torch.device | None = None) -> tuple[float, list[float]]:
    """
    Start from a blank baseline (zeros) and progressively insert the
    most-attributed pixels from the original image.

    Returns (auc, curve). Higher AUC = more faithful explanation.
    """
    if device is None:
        device = next(model.parameters()).device

    model.eval()
    image_tensor = image_tensor.to(device)
    H, W = image_tensor.shape[-2], image_tensor.shape[-1]
    heatmap = _normalize_heatmap_size(heatmap, (H, W))

    original = _target_prob(model, image_tensor, target_class=1)
    target_class = 1 if original >= 0.5 else 0

    sorted_idx = _rank_pixels_by_importance(heatmap)
    n_pixels = H * W
    pixels_per_step = max(1, n_pixels // steps)

    current = torch.zeros_like(image_tensor)
    curve: list[float] = [_target_prob(model, current, target_class)]

    for step in range(1, steps + 1):
        start = (step - 1) * pixels_per_step
        end = min(step * pixels_per_step, n_pixels)
        idx_slice = sorted_idx[start:end]
        ys, xs = np.divmod(idx_slice, W)
        current[0, :, ys, xs] = image_tensor[0, :, ys, xs]
        curve.append(_target_prob(model, current, target_class))

    x = np.linspace(0, 1, len(curve))
    auc = float(np.trapezoid(curve, x))
    return auc, curve


# ─────────────────────────────────────────────────────────────────────────
# Cross-method agreement
# ─────────────────────────────────────────────────────────────────────────

def heatmap_correlation(heatmap_a: np.ndarray,
                        heatmap_b: np.ndarray) -> tuple[float, float]:
    """
    Pearson and Spearman correlation of absolute pixel attributions.
    Returns (pearson_r, spearman_r). 1.0 = perfect agreement, 0 = no agreement.
    """
    if heatmap_a.shape != heatmap_b.shape:
        heatmap_b = _normalize_heatmap_size(heatmap_b, heatmap_a.shape)
    a = np.abs(heatmap_a).flatten()
    b = np.abs(heatmap_b).flatten()

    if a.std() < 1e-10 or b.std() < 1e-10:
        return 0.0, 0.0

    p, _ = pearsonr(a, b)
    s, _ = spearmanr(a, b)
    return float(p), float(s)


def iou_at_topk(heatmap_a: np.ndarray, heatmap_b: np.ndarray,
                k: float = 20.0) -> float:
    """
    Intersection-over-union of the top-K% pixels (by absolute attribution).
    1.0 = perfect overlap, 0 = no overlap.
    """
    if heatmap_a.shape != heatmap_b.shape:
        heatmap_b = _normalize_heatmap_size(heatmap_b, heatmap_a.shape)
    a = np.abs(heatmap_a).flatten()
    b = np.abs(heatmap_b).flatten()

    thr_a = np.percentile(a, 100 - k)
    thr_b = np.percentile(b, 100 - k)
    mask_a = a >= thr_a
    mask_b = b >= thr_b

    intersection = int((mask_a & mask_b).sum())
    union = int((mask_a | mask_b).sum())
    return intersection / max(union, 1)


# ─────────────────────────────────────────────────────────────────────────
# Sparsity
# ─────────────────────────────────────────────────────────────────────────

def sparsity(heatmap: np.ndarray, threshold_pct: float = 5.0) -> float:
    """
    Fraction of pixels whose absolute attribution is below
    threshold_pct% of the maximum.

    Higher sparsity = more localized explanation.
    """
    flat = np.abs(heatmap).flatten()
    if flat.max() < 1e-10:
        return 1.0
    threshold = (threshold_pct / 100.0) * flat.max()
    return float((flat < threshold).mean())


# ─────────────────────────────────────────────────────────────────────────
# Full report for one image
# ─────────────────────────────────────────────────────────────────────────

def evaluate_one(model: nn.Module,
                 image_tensor: torch.Tensor,
                 heatmaps: dict[str, np.ndarray],
                 steps: int = 20,
                 device: torch.device | None = None) -> dict:
    """
    Run all metrics on one image's heatmaps.

    Args:
        model:         the trained classifier
        image_tensor:  (1, 3, H, W) preprocessed tensor
        heatmaps:      {'gradcam': arr, 'shap': arr, 'lime': arr}
        steps:         number of pixel-batches for deletion/insertion

    Returns a nested dict:
        {
            'gradcam': {'deletion_auc': X, 'insertion_auc': X,
                        'sparsity': X, 'del_curve': [...], 'ins_curve': [...]},
            ...
            'cross_method': {
                'gradcam_shap': {'pearson': X, 'spearman': X, 'iou_top20': X},
                ...
            }
        }
    """
    per_method = {}
    for name, hm in heatmaps.items():
        del_auc, del_curve = deletion_auc(model, image_tensor, hm,
                                          steps=steps, device=device)
        ins_auc, ins_curve = insertion_auc(model, image_tensor, hm,
                                           steps=steps, device=device)
        per_method[name] = {
            "deletion_auc": del_auc,
            "insertion_auc": ins_auc,
            "sparsity": sparsity(hm),
            "del_curve": del_curve,
            "ins_curve": ins_curve,
        }

    # Pairwise comparisons
    cross = {}
    names = sorted(heatmaps.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            p, s = heatmap_correlation(heatmaps[a], heatmaps[b])
            iou = iou_at_topk(heatmaps[a], heatmaps[b], k=20.0)
            cross[f"{a}_{b}"] = {
                "pearson": p,
                "spearman": s,
                "iou_top20": iou,
            }

    return {"per_method": per_method, "cross_method": cross}

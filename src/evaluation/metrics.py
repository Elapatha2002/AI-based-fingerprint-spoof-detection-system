"""
Biometric-specific metrics from proposal §4.6.1.

  APCER = % of spoof (attack) samples wrongly classified as live
  BPCER = % of live (bona-fide) samples wrongly classified as spoof
  ACE   = (APCER + BPCER) / 2
  EER   = the operating-point threshold where APCER == BPCER

Plus standard scikit-learn: accuracy, precision, recall, F1, ROC-AUC.

All metrics expect:
    y_true : 1D int  array (0=live, 1=spoof)
    y_prob : 1D float array (P(spoof))
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix,
)


def apcer(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """% of spoofs wrongly accepted as live."""
    spoof_mask = y_true == 1
    if spoof_mask.sum() == 0:
        return 0.0
    return float(100.0 * np.mean(y_pred[spoof_mask] == 0))


def bpcer(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """% of live wrongly rejected as spoof."""
    live_mask = y_true == 0
    if live_mask.sum() == 0:
        return 0.0
    return float(100.0 * np.mean(y_pred[live_mask] == 1))


def ace(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return (apcer(y_true, y_pred) + bpcer(y_true, y_pred)) / 2.0


def eer(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[float, float]:
    """
    Equal Error Rate and the threshold at which it occurs.
    Returns (eer_percent, threshold).
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    fnr = 1 - tpr
    # Where |FPR - FNR| is minimized
    diffs = np.abs(fpr - fnr)
    idx = int(np.argmin(diffs))
    eer_val = float((fpr[idx] + fnr[idx]) / 2.0 * 100.0)
    return eer_val, float(thresholds[idx])


def all_metrics(y_true: np.ndarray, y_prob: np.ndarray,
                threshold: float = 0.5) -> dict:
    """Returns a flat dict of every metric, computed at a fixed threshold."""
    y_pred = (y_prob >= threshold).astype(int)

    eer_pct, eer_thr = eer(y_true, y_prob)

    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "apcer": apcer(y_true, y_pred),
        "bpcer": bpcer(y_true, y_pred),
        "ace": ace(y_true, y_pred),
        "eer": eer_pct,
        "eer_threshold": eer_thr,
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "n_total": int(len(y_true)),
        "n_live": int((y_true == 0).sum()),
        "n_spoof": int((y_true == 1).sum()),
    }


def format_metrics(m: dict) -> str:
    """Pretty multi-line summary for stdout."""
    return (
        f"  AUC      : {m['roc_auc']:.4f}\n"
        f"  Accuracy : {m['accuracy']:.4f}\n"
        f"  APCER    : {m['apcer']:.2f}%\n"
        f"  BPCER    : {m['bpcer']:.2f}%\n"
        f"  ACE      : {m['ace']:.2f}%\n"
        f"  EER      : {m['eer']:.2f}%  @ thr={m['eer_threshold']:.3f}\n"
        f"  F1       : {m['f1']:.4f}\n"
        f"  CM       : {m['confusion_matrix']}"
    )

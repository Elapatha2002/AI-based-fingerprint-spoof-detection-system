"""Screen 9 — About / Methodology."""
import json
import os
from pathlib import Path

import streamlit as st
from components.cards import page_title, section_header, divider, banner


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RESULTS_DIR = _PROJECT_ROOT / "results"

# Documented fall-back for the "Model" card if no live test-metrics file
# is discoverable (e.g. running in mock mode with no checkpoints).
_FALLBACK = {
    "arch":  "FSD-CBAM v2",
    "ckpt":  "fsd_cbam_v2_20260810_122231",
    "accuracy": 0.9536,
    "roc_auc":  0.9919,
    "apcer": 5.87,
    "bpcer": 3.32,
    "ace":   4.60,
}


def _resolve_model_card() -> tuple[float, float, float, float, float, str, str]:
    """Return (accuracy, auc, apcer, bpcer, ace, arch, ckpt_short) for the
    Model card. Prefers the currently-selected checkpoint's test-metrics
    file; falls back to documented FSD-CBAM v2 numbers if unavailable."""
    ckpt_short = _FALLBACK["ckpt"]
    arch = _FALLBACK["arch"]

    if os.environ.get("FSDXAI_REAL_MODEL") == "1":
        try:
            # The methodology page needs configuration and metrics, not model
            # weights. Keep navigation here independent of PyTorch/checkpoint I/O.
            from app.services.model_config import configured_selection
            arch, checkpoint = configured_selection(st.session_state)
            ckpt_short = checkpoint.parent.name or ckpt_short
        except Exception:
            pass

    metrics_path = _RESULTS_DIR / f"{ckpt_short}_test_metrics.json"
    if metrics_path.exists():
        try:
            m = json.loads(metrics_path.read_text())
            return (m.get("accuracy", _FALLBACK["accuracy"]),
                    m.get("roc_auc",  _FALLBACK["roc_auc"]),
                    m.get("apcer",    _FALLBACK["apcer"]),
                    m.get("bpcer",    _FALLBACK["bpcer"]),
                    m.get("ace",      _FALLBACK["ace"]),
                    arch, ckpt_short)
        except (json.JSONDecodeError, OSError):
            pass

    return (_FALLBACK["accuracy"], _FALLBACK["roc_auc"],
            _FALLBACK["apcer"], _FALLBACK["bpcer"], _FALLBACK["ace"],
            arch, ckpt_short)


def render():
    page_title("Methodology and limitations",
               "Understand the evidence, model basis, and limits before relying on an output.")

    banner(
        "Research decision-support only. A qualified examiner must review the "
        "input, predicted outcome, and visual explanations before a forensic decision.",
        kind="warn",
    )

    cols = st.columns([1, 3])

    with cols[0]:
        st.markdown(
            """
            <div class='fsd-card' style='position:sticky;top:80px;'>
              <div class='fsd-section-h' style='margin:0 0 8px 0;'>Use outputs responsibly</div>
              <div style='font-size:13px;color:var(--text-secondary);line-height:1.65;'>
                <b>1. Check image quality</b> before interpreting a result.<br/><br/>
                <b>2. Review all XAI views</b>; an overlay is supporting evidence,
                not independent proof.<br/><br/>
                <b>3. Record context</b> such as the sensor and examiner in the
                case record.<br/><br/>
                <b>4. Use professional judgement</b> for every conclusion.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        section_header("Overview")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "This system detects spoofed fingerprints (silicone, gelatin, latex, "
            "wood glue, Play-Doh, ecoflex, etc.) using a convolutional neural "
            "network with attention, and explains its decisions using three XAI "
            "techniques: <b>Grad-CAM++</b>, <b>SHAP</b>, and <b>LIME</b>."
            "</div>",
            unsafe_allow_html=True,
        )

        section_header("How it works")
        st.markdown(
            "<ol style='color:var(--text-secondary);line-height:1.8;'>"
            "<li>Each uploaded fingerprint is preprocessed: RGB conversion, "
            "resize to 224 x 224, and ImageNet normalisation.</li>"
            "<li>A CNN (default: the novel <b>FSD-CBAM v2</b> attention "
            "module on a ResNet50 backbone) produces a live-vs-spoof "
            "probability.</li>"
            "<li>Three XAI methods generate visual explanations: "
            "Grad-CAM++, SHAP GradientExplainer, and LIME with quickshift "
            "superpixels.</li>"
            "<li>Every action is dual-written to a session audit log and to "
            "a persistent SQLite database, giving the workflow a chain of "
            "custody that survives restarts.</li>"
            "<li>A Daubert/Frye-aligned PDF report is composed with case "
            "metadata, the classification, the three XAI overlays, and a "
            "methodology declaration.</li>"
            "</ol>",
            unsafe_allow_html=True,
        )

        section_header("Datasets")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "Trained and evaluated on the harmonised <b>LivDet "
            "2009 + 2011 + 2013 + 2015</b> corpus (65,267 images, 9 sensors, "
            "12 spoof materials). Externally validated on the <b>SOCOFing</b> "
            "cross-demographic bona-fide dataset (6,000 images, SecuGen "
            "Hamster Plus sensor). All datasets are public; no PII; "
            "image hashes preserved.</div>",
            unsafe_allow_html=True,
        )

        section_header("Model")
        # Prefer live numbers from the loaded checkpoint's test-metrics
        # file when available; fall back to the documented FSD-CBAM v2
        # figures if the file is missing.
        acc, auc, apcer, bpcer, ace, arch, ckpt = _resolve_model_card()
        st.markdown(
            f"""
            <div class='fsd-card'>
            <div class='fsd-mono' style='line-height:1.9;'>
              Architecture &nbsp;:&nbsp; <b>{arch}</b>  &nbsp;(novel — multi-scale channel + focused 7x7 spatial attention)<br/>
              Alternate &nbsp;&nbsp;&nbsp;:&nbsp; MobileNetV3-Large  (4.2M params, edge-friendly)<br/>
              Training data &nbsp;:&nbsp; LivDet 2009-2015  (35,427 train / 29,840 test)<br/>
              AUC &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; <b>{auc:.4f}</b>  (Pareto-optimal)<br/>
              Accuracy &nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; <b>{acc*100:.2f}%</b><br/>
              APCER &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; <b>{apcer:.2f}%</b>  (best of five backbones tested)<br/>
              BPCER &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; {bpcer:.2f}%<br/>
              ACE &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp; {ace:.2f}%<br/>
              Checkpoint &nbsp;:&nbsp; {ckpt}
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_header("XAI methods")
        st.markdown(
            "<ul style='color:var(--text-secondary);line-height:1.8;'>"
            "<li><b>Grad-CAM++</b> — gradient-based heatmaps; best for "
            "ridge / pore localization.</li>"
            "<li><b>SHAP</b> — feature attribution via Shapley values; "
            "shows positive and negative contributions.</li>"
            "<li><b>LIME</b> — local linear approximation over superpixels.</li>"
            "</ul>",
            unsafe_allow_html=True,
        )

        section_header("Limitations")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "This is a research prototype. It does <b>not</b> cover: 3D-printed "
            "conductive spoofs, AI-generated ridge patterns, body-double prints, "
            "or live-signal biometrics (pulse, temperature). It uses 2D images "
            "only and was trained predominantly on optical sensors. "
            "See thesis §4.8 for full discussion.</div>",
            unsafe_allow_html=True,
        )

        section_header("Forensic admissibility")
        st.markdown(
            "<div style='color:var(--text-secondary);line-height:1.7;'>"
            "System outputs are designed against Daubert / Frye criteria: "
            "testability, peer-review potential, and known error rates. "
            "Practitioner usability is validated through expert survey "
            "(thesis Chapter 5). Every report PDF embeds the model commit "
            "hash and dataset version for reproducibility.</div>",
            unsafe_allow_html=True,
        )

        section_header("References")
        st.markdown(
            """
            <div class='fsd-mono' style='font-size:12px;color:var(--text-muted);
                 line-height:1.9;'>
              [1] Mukul & Lal (2022). Fingerprint Liveness Detection Using CNN-Based Hybrid Model. <i>NeuroQuantology</i>.<br/>
              [2] Chugh & Jain (2018). Fingerprint Spoof Detector Generalization. <i>IEEE TIFS</i>.<br/>
              [3] Cheniti et al. (2025). Dual-Model Synergy for Fingerprint Spoof Detection. <i>J. Imaging</i>.<br/>
              [4] Zhang et al. (2019). Slim-ResCNN. <i>IEEE Access</i>.<br/>
              [5] Kothadiya et al. (2023). Enhancing Fingerprint Liveness Detection Accuracy. <i>J. Imaging</i>.<br/>
              [6] Naeem et al. (2025). Revolutionizing Biometric Security. <i>IJAMRS</i>.<br/>
              [7] Uliyan et al. (2020). Anti-spoofing method for fingerprint recognition. <i>JESTECH</i>.<br/>
              [8] Agarwal & Bansal (2022). Fingerprint liveness detection through fusion of pores. <i>JKSU-CIS</i>.
            </div>
            """,
            unsafe_allow_html=True,
        )

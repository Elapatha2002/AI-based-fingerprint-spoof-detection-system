"""Screen 5 — Single Result (also reused by drilldown)."""
import streamlit as st
from io import BytesIO
from PIL import Image

from components.cards import (
    page_title, divider, section_header,
    verdict_card, quality_card, anomaly_card, timing_card, banner,
    tech_strip,
)
from components.xai_views import xai_tabs
from components.case_strip import render_case_strip
from components.confidence_gauge import render_confidence_gauge
from components.xai_interpretation import render_xai_interpretation
from components.audit import render_audit_drawer, log_action
from services import mock_model
from utils.image_loader import load_image


@st.cache_data(show_spinner=False)
def _cached_predict(filename: str, image_bytes: bytes) -> dict:
    img = Image.open(BytesIO(image_bytes)) if image_bytes else None
    return mock_model.predict(filename, img)


@st.cache_data(show_spinner=False)
def _cached_explain(filename: str, image_bytes: bytes) -> dict:
    img = Image.open(BytesIO(image_bytes)) if image_bytes else None
    return mock_model.explain(filename, img)


def render(from_drilldown: bool = False, drilldown_meta: dict | None = None):
    """If from_drilldown, drilldown_meta carries the file context."""
    if from_drilldown and drilldown_meta:
        single = drilldown_meta
    else:
        single = st.session_state.get("current_single")

    if not single:
        st.warning("No image to display.")
        if st.button("Go to Analyze"):
            st.session_state.current_page = "analyze"
            st.rerun()
        return

    filename = single["filename"]
    image_bytes = single.get("image_bytes")
    meta = single.get("meta", {})

    img, err = (None, None)
    if image_bytes:
        img, err = load_image(BytesIO(image_bytes))
    if img is None and err:
        banner(f"Could not display image: {err}", kind="warn")
        img = mock_model.placeholder_image(filename)
    elif img is None:
        img = mock_model.placeholder_image(filename)

    # Case-context strip (persistent on every result view)
    from datetime import datetime
    strip_meta = dict(meta)
    strip_meta.setdefault("timestamp",
                          datetime.now().isoformat(timespec="seconds"))
    render_case_strip(strip_meta,
                      status=st.session_state.get("case_status", "In Review"))

    page_title(
        f"Result · {filename}",
        f"Forensic spoof detection · explainable AI",
    )

    with st.spinner("Running classifier..."):
        result = _cached_predict(filename, image_bytes or b"")

    # Audit the classification once per (filename, case_id) combination
    audit_key = f"audit_classify_{meta.get('case_id', '—')}_{filename}"
    if not st.session_state.get(audit_key):
        log_action(
            action=f"Classified {filename}",
            case_id=meta.get("case_id", "—"),
            details=(
                f"verdict={result['label'].upper()}, "
                f"P(spoof)={result['raw_score']:.4f}, "
                f"model={result['model']['name']}"
            ),
        )
        st.session_state[audit_key] = True

    if result.get("borderline"):
        banner("Borderline confidence — re-capture is recommended.", kind="warn")

    if not result["known_pattern"]:
        banner("Anomaly detector flagged this image as unusual. "
               "The verdict is provisional.", kind="warn")

    # Two-column layout: image on left, cards on right
    cols = st.columns([1.4, 1])

    with cols[0]:
        st.image(img, caption=f"{filename} · {img.size[0]}x{img.size[1]}",
                 use_container_width=True)

    with cols[1]:
        # TIER 1 — Hero verdict + confidence gauge
        verdict_card(result["label"], result["confidence"],
                     result.get("material"), result.get("borderline", False),
                     hero=True)
        render_confidence_gauge(
            result["raw_score"],
            eer_threshold=st.session_state.get("eer_threshold", 0.22),
        )

        # TIER 2 — Quality + anomaly (compact row)
        sub_a, sub_b = st.columns(2)
        with sub_a:
            quality_card(result["nfiq2"], result["quality_tier"])
        with sub_b:
            anomaly_card(result["anomaly_score"],
                         result["known_pattern"],
                         result["vae_recon_error"])

        # TIER 3 — Tech provenance strip
        tech_strip([
            f"⚡ {result['timing_ms']['total']} ms",
            f"🔧 {result['model']['name']}",
            f"#{result['model']['commit']}",
        ])

    # Diagnostic panel — shows raw model outputs for debugging
    with st.expander("🔍 Diagnostic info (raw model output)", expanded=False):
        import hashlib
        img_hash = hashlib.md5(image_bytes or b"").hexdigest()[:12] if image_bytes else "no-bytes"
        st.markdown(
            f"""
            <div class='fsd-mono' style='font-size:12px;line-height:1.9;'>
              <b>Raw P(spoof)</b>:       <span style='color:var(--accent-info)'>{result['raw_score']:.6f}</span><br/>
              <b>Threshold</b>:          0.500 (default)<br/>
              <b>Decision</b>:           {result['label'].upper()}
              ({'P(spoof) ≥ 0.5' if result['raw_score'] >= 0.5 else 'P(spoof) < 0.5'})<br/>
              <b>Model loaded</b>:       {result['model']['name']} · commit {result['model']['commit']}<br/>
              <b>Image hash (MD5)</b>:   {img_hash}<br/>
              <b>Image size shown</b>:   {img.size[0]} × {img.size[1]} px<br/>
              <b>Filename</b>:           {filename}
            </div>
            <br/>
            <div style='color:var(--text-muted);font-size:11px;'>
              If P(spoof) is near 0 for a known spoof, the model is genuinely failing —
              not a UI bug. If P(spoof) is near 1 but the verdict shows LIVE, that's a
              display bug. If the image hash changes between uploads, the cache is
              correctly seeing fresh data.
            </div>
            """,
            unsafe_allow_html=True,
        )

    divider()

    section_header("Explanation")
    with st.spinner("Computing XAI overlays..."):
        xai_panels = _cached_explain(filename, image_bytes or b"")

    xai_tabs(xai_panels, original_image=img)

    # Guided interpretation panel — explains what the heatmaps mean together
    render_xai_interpretation(
        xai_panels,
        verdict_label=result["label"],
        p_spoof=result["raw_score"],
    )

    divider()

    # Audit trail for this case
    render_audit_drawer(case_id=meta.get("case_id"), expanded=False)

    divider()

    # Action row
    a1, a2, a3, _ = st.columns([1, 1, 1, 3])
    with a1:
        if st.button("📑  Generate PDF", type="primary",
                     use_container_width=True, key="sr_report"):
            log_action(
                action=f"Initiated report generation for {filename}",
                case_id=meta.get("case_id", "—"),
            )
            st.session_state.current_report_target = {
                "filename": filename,
                "image_bytes": image_bytes,
                "meta": meta,
                "result": result,
                "xai": xai_panels,
            }
            st.session_state.current_page = "report_preview"
            st.rerun()

    with a2:
        if st.button("🔬  Compare All", use_container_width=True,
                     key="sr_compare"):
            st.session_state["compare_target"] = {
                "filename": filename,
                "image_bytes": image_bytes,
            }
            st.session_state.current_page = "compare_xai"
            st.rerun()

    with a3:
        if st.button("💾  Save to History", use_container_width=True,
                     key="sr_save"):
            from state import add_to_history
            add_to_history({
                "type": "single",
                "case_id": meta.get("case_id", "—"),
                "count": 1,
                "live_count": 1 if result["label"] == "live" else 0,
                "spoof_count": 1 if result["label"] == "spoof" else 0,
                "status": "Done",
                "result": result,
                "meta": meta,
                "filename": filename,
            })
            st.toast("Saved to history.")

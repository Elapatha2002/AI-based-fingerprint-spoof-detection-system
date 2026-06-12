"""Screen 5 — Single Result (also reused by drilldown)."""
import streamlit as st
from io import BytesIO
from PIL import Image

from components.cards import (
    page_title, divider, section_header,
    verdict_card, quality_card, anomaly_card, timing_card, banner,
)
from components.xai_views import xai_tabs
from services import mock_model
from utils.image_loader import load_image


@st.cache_data(show_spinner=False)
def _cached_predict(filename: str, image_bytes: bytes) -> dict:
    return mock_model.predict(filename)


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

    page_title(
        f"Result · {meta.get('case_id', '—')} · {filename}",
        f"Examined by {meta.get('examiner', '—')} · {meta.get('sensor', '—')}",
    )

    with st.spinner("Running classifier..."):
        result = _cached_predict(filename, image_bytes or b"")

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
        verdict_card(result["label"], result["confidence"],
                     result.get("material"), result.get("borderline", False))
        quality_card(result["nfiq2"], result["quality_tier"])
        anomaly_card(result["anomaly_score"],
                     result["known_pattern"],
                     result["vae_recon_error"])
        timing_card(result["timing_ms"])

    divider()

    section_header("Explanation")
    with st.spinner("Computing XAI overlays..."):
        xai_panels = _cached_explain(filename, image_bytes or b"")

    xai_tabs(xai_panels, original_image=img)

    divider()

    # Action row
    a1, a2, a3, _ = st.columns([1, 1, 1, 3])
    with a1:
        if st.button("📑  Generate PDF", type="primary",
                     use_container_width=True, key="sr_report"):
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

"""Read-only history: display stored results without invoking inference/XAI."""
import hashlib
from io import BytesIO
import logging

from PIL import Image
import streamlit as st

from app.services import database, storage
from components.cards import page_title

logger = logging.getLogger(__name__)


class EvidenceIntegrityError(ValueError):
    """The downloaded file is not the evidence recorded with this analysis."""


def _load_evidence(row: dict) -> Image.Image:
    """Validate the exact saved object's identity before displaying it."""
    data = storage.get_storage().download_bytes(row["image_s3_key"])
    if row.get("image_hash") and hashlib.sha256(data).hexdigest() != row["image_hash"]:
        raise EvidenceIntegrityError("The stored image does not match the recorded SHA-256 hash.")
    with Image.open(BytesIO(data)) as image:
        image.load()
        return image.copy()


def _number(value, spec=".2f") -> str:
    return "Not recorded" if value is None else format(value, spec)


def render():
    if st.button("Back to history", key="saved_back"):
        st.session_state.current_page = "history"
        st.rerun()

    case_id = st.session_state.get("saved_case_id")
    if not case_id:
        st.warning("Choose a saved analysis from History.")
        return
    page_title("Saved analysis", f"Case {case_id}")
    try:
        rows = database.list_analyses(case_id=case_id, limit=None)
    except Exception:
        logger.exception("Could not read saved analyses")
        st.error("Saved records could not be loaded. Check the database connection and try again.")
        return
    if not rows:
        st.warning("No saved analyses are available for this case.")
        return

    st.caption("Stored results only — opening a record does not run the model again. "
               "Repeat saves and earlier model results are retained below.")
    by_id = {row["analysis_id"]: row for row in rows}
    ids = list(by_id)
    preferred = st.session_state.get("saved_analysis_id")
    choice = st.selectbox(
        "Saved record", ids,
        index=ids.index(preferred) if preferred in ids else 0,
        format_func=lambda aid: (
            f"{by_id[aid]['image_filename']} · {by_id[aid]['created_at']} · "
            f"{by_id[aid]['model_name']} · {aid}"
        ),
        key=f"saved_record_{case_id}",
    )
    row = by_id[choice]
    st.session_state.saved_analysis_id = choice

    image_col, result_col = st.columns([1, 1.4])
    with image_col:
        try:
            with st.spinner("Loading saved fingerprint..."):
                image = _load_evidence(row)
            st.image(image, caption=row["image_filename"], width="stretch")
            if row.get("image_hash"):
                st.caption("Image matches the recorded SHA-256 hash.")
            else:
                st.caption("This legacy record has no image hash to verify.")
        except EvidenceIntegrityError:
            st.error("Image integrity check failed: the stored file does not match "
                     "this record. The saved result is still shown; do not use "
                     "the file as verified evidence.")
        except Exception:
            logger.exception("Could not load saved evidence for %s", choice)
            st.warning("The original image could not be loaded. Check the evidence "
                       "storage connection or restore the missing file. "
                       "The saved result is still available.")
    with result_col:
        st.metric("Saved verdict", row["verdict"].upper())
        st.metric("Confidence", _number(row.get("confidence"), ".1%"))
        st.dataframe([
            {"Field": "Model", "Saved value": row["model_name"]},
            {"Field": "Decision threshold", "Saved value": _number(row.get("threshold_used"))},
            {"Field": "Inference time (ms)", "Saved value": _number(row.get("inference_ms"))},
            {"Field": "Saved at (UTC)", "Saved value": row["created_at"]},
            {"Field": "Analysis ID", "Saved value": choice},
            {"Field": "Image SHA-256", "Saved value": row.get("image_hash") or "Not recorded"},
        ], hide_index=True, width="stretch")

    st.subheader("Saved explanations")
    st.caption("Only persisted heatmaps and scores are shown. Other explanation "
               "and image-quality metrics were not stored in these records.")
    try:
        panels = database.list_xai_for_analysis(choice)
    except Exception:
        logger.exception("Could not read saved explanations for %s", choice)
        st.warning("Saved explanations could not be loaded. Check the database connection.")
        return
    if not panels:
        st.info("No explanations were saved with this record.")
        return
    names = {"gradcam": "Grad-CAM++", "shap": "SHAP", "lime": "LIME"}
    cols = st.columns(min(3, len(panels)))
    for index, panel in enumerate(panels):
        with cols[index % len(cols)]:
            method = names.get(panel["method"], panel["method"])
            st.markdown(f"**{method}**")
            try:
                data = storage.get_storage().download_bytes(panel["heatmap_s3_key"])
                with Image.open(BytesIO(data)) as image:
                    image.load()
                    st.image(image.copy(), width="stretch")
            except Exception:
                logger.exception("Could not load saved %s heatmap for %s", method, choice)
                st.warning(f"The saved {method} heatmap is unavailable. Check evidence storage.")
            if panel.get("faithfulness") is not None:
                st.caption(f"Saved faithfulness: {panel['faithfulness']:.3f}")

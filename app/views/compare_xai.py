"""Screen 10 — XAI Comparison."""
import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image

from components.cards import (
    page_title, section_header, divider, banner, empty_state,
)
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


def render():
    page_title("XAI Comparison",
               "Compare Grad-CAM++, SHAP, and LIME on the same fingerprint.")

    target = st.session_state.get("compare_target")
    batch = st.session_state.get("current_batch")
    single = st.session_state.get("current_single")

    if not target:
        if batch and batch.get("results"):
            target = {
                "filename": batch["files"][0][0] if batch.get("files") else
                           batch["results"][0]["filename"],
                "image_bytes": batch["files"][0][1] if batch.get("files") else b"",
            }
        elif single:
            target = {
                "filename": single["filename"],
                "image_bytes": single.get("image_bytes", b""),
            }

    if not target:
        empty_state(
            icon="🔬",
            message="No image loaded. Run an analysis first, or open this "
                    "view from a Single Result page.",
            title="Choose an analysis to compare",
            action_label="Go to Analyze",
            action_page="analyze",
            key="empty_compare_start",
        )
        return

    # Image picker (if from a batch, allow choosing among batch images)
    if batch and batch.get("files"):
        picker_cols = st.columns([3, 1])
        with picker_cols[0]:
            names = [f for f, _ in batch["files"]]
            current_idx = next(
                (i for i, n in enumerate(names) if n == target["filename"]), 0
            )
            sel = st.selectbox("Image", names, index=current_idx,
                               key="cmp_picker")
            if sel != target["filename"]:
                target = {
                    "filename": sel,
                    "image_bytes": next(
                        d for f, d in batch["files"] if f == sel
                    ),
                }
                st.session_state["compare_target"] = target

    filename = target["filename"]
    image_bytes = target.get("image_bytes", b"")

    img, _ = load_image(BytesIO(image_bytes)) if image_bytes else (None, None)
    if img is None:
        img = mock_model.placeholder_image(filename)

    with st.spinner("Loading prediction..."):
        result = _cached_predict(filename, image_bytes)

    # The comparison page must never trigger all three explainers in a single
    # hosted request.  The result page generates them independently and passes
    # the completed panels here.
    xai = target.get("xai", {})
    required = {"gradcam", "shap", "lime"}
    if not required.issubset(xai):
        st.info(
            "Generate Grad-CAM++, SHAP and LIME on the Result page first. "
            "They will then be available here for comparison."
        )
        if st.button("Open Result", type="primary", key="cmp_generate_first"):
            st.session_state.current_single = {
                "filename": filename,
                "image_bytes": image_bytes,
                "meta": (batch["meta"] if batch else
                         single.get("meta", {}) if single else {}),
            }
            st.session_state.current_page = "single_result"
            st.rerun()
        return

    if any(p.get('status') == 'error' for p in xai.values()):
        from components.xai_views import xai_tabs
        st.warning('Explanation generation is incomplete. Method rankings are unavailable.')
        xai_tabs(xai, original_image=img)
        return

    # 2x3 grid
    row1 = st.columns(3)
    with row1[0]:
        st.image(img, caption="Original", width="stretch")
        st.markdown(
            f"<div class='fsd-mono' style='font-size:11px;'>"
            f"{img.size[0]}x{img.size[1]} px · {filename}</div>",
            unsafe_allow_html=True,
        )
    with row1[1]:
        st.image(xai["gradcam"]["image"], caption="Grad-CAM++",
                 width="stretch")
        st.markdown(
            f"<div class='fsd-mono' style='font-size:11px;'>"
            f"Top region: central ridge</div>",
            unsafe_allow_html=True,
        )
    with row1[2]:
        verdict_color = ("var(--accent-spoof)" if result["label"] == "spoof"
                         else "var(--accent-live)")
        st.markdown(
            f"""
            <div class='fsd-card' style='text-align:center;padding:24px;'>
              <div class='fsd-card-title'>Verdict</div>
              <div class='fsd-card-value' style='color:{verdict_color};
                   font-size:28px;'>{result['label'].upper()}</div>
              <div class='fsd-card-sub'>{result['confidence']:.2%} confidence</div>
              <div class='fsd-card-sub' style='margin-top:8px;'>
                Material: <b>{result.get('material') or '—'}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    row2 = st.columns(3)
    with row2[0]:
        st.image(xai["shap"]["image"], caption="SHAP",
                 width="stretch")
        st.markdown(
            "<div class='fsd-mono' style='font-size:11px;'>"
            "+ red = positive · − blue = negative</div>",
            unsafe_allow_html=True,
        )
    with row2[1]:
        st.image(xai["lime"]["image"], caption="LIME",
                 width="stretch")
        st.markdown(
            "<div class='fsd-mono' style='font-size:11px;'>"
            "Top 5 superpixels highlighted</div>",
            unsafe_allow_html=True,
        )
    with row2[2]:
        st.markdown(
            f"""
            <div class='fsd-card'>
              <div class='fsd-card-title'>Faithfulness Scores</div>
              <div class='fsd-mono' style='line-height:2;font-size:13px;
                   margin-top:8px;'>
                Grad-CAM++ &nbsp;&nbsp; <b>{xai['gradcam']['faithfulness']:.2f}</b><br/>
                SHAP &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                <b>{xai['shap']['faithfulness']:.2f}</b><br/>
                LIME &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                <b>{xai['lime']['faithfulness']:.2f}</b>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    divider()

    section_header("Quantitative comparison")
    # Only display metrics the pipeline actually computes per-image
    # (faithfulness, IoU, compute time). Stability across re-runs was
    # never measured here and used to be hardcoded — that column has
    # been removed to avoid misleading the reader.
    metrics_df = pd.DataFrame({
        "Metric": ["Faithfulness (del-AUC)", "Localisation (IoU)",
                   "Compute time"],
        "Grad-CAM++": [
            f"{xai['gradcam']['faithfulness']:.2f}",
            f"{xai['gradcam']['localization_iou']:.2f}",
            f"{xai['gradcam']['compute_ms']} ms",
        ],
        "SHAP": [
            f"{xai['shap']['faithfulness']:.2f}",
            f"{xai['shap']['localization_iou']:.2f}",
            f"{xai['shap']['compute_ms']/1000:.2f} s",
        ],
        "LIME": [
            f"{xai['lime']['faithfulness']:.2f}",
            f"{xai['lime']['localization_iou']:.2f}",
            f"{xai['lime']['compute_ms']/1000:.2f} s",
        ],
    })
    st.dataframe(metrics_df, width="stretch", hide_index=True)

    best = max(["gradcam", "shap", "lime"],
               key=lambda k: xai[k]["faithfulness"])
    fastest = min(["gradcam", "shap", "lime"],
                  key=lambda k: xai[k]["compute_ms"])
    pretty = {"gradcam": "Grad-CAM++", "shap": "SHAP", "lime": "LIME"}

    st.markdown(
        f"<div style='color:var(--text-secondary);margin-top:12px;line-height:1.7;'>"
        f"<b>Plain-language summary:</b> on this image, "
        f"<b>{pretty[best]}</b> records the highest faithfulness score "
        f"({xai[best]['faithfulness']:.2f}), while <b>{pretty[fastest]}</b> "
        f"produces its overlay fastest at {xai[fastest]['compute_ms']} ms. "
        f"Cross-method aggregate faithfulness statistics are reported "
        f"in the thesis Section 4.9.</div>",
        unsafe_allow_html=True,
    )

    divider()

    a1, a2, _ = st.columns([1, 1, 4])
    with a1:
        if st.button("⬇  Export CSV", width="stretch",
                     key="cmp_export"):
            csv = metrics_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download metrics.csv", data=csv,
                               file_name=f"xai_comparison_{filename}.csv",
                               mime="text/csv", key="cmp_dl")
    with a2:
        if st.button("Open in Result", width="stretch",
                     key="cmp_open"):
            st.session_state.current_single = {
                "filename": filename,
                "image_bytes": image_bytes,
                "meta": batch["meta"] if batch else {"case_id": "—",
                                                      "examiner": "—"},
            }
            st.session_state.current_page = "single_result"
            st.rerun()

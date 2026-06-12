"""XAI tab panel rendering."""
import streamlit as st


def xai_tabs(xai_panels: dict, original_image=None):
    """Render Grad-CAM++ / SHAP / LIME / All tabs given a panels dict."""
    tab_grad, tab_shap, tab_lime, tab_all = st.tabs(
        ["Grad-CAM++", "SHAP", "LIME", "All"]
    )

    with tab_grad:
        _single_panel(xai_panels.get("gradcam"), "Grad-CAM++", original_image,
                      legend="viridis (low → high attribution)")
    with tab_shap:
        _single_panel(xai_panels.get("shap"), "SHAP", original_image,
                      legend="red = positive evidence · blue = negative")
    with tab_lime:
        _single_panel(xai_panels.get("lime"), "LIME", original_image,
                      legend="superpixels driving the decision")
    with tab_all:
        _all_panels_grid(xai_panels, original_image)


def _single_panel(panel: dict, name: str, original_image, legend: str):
    if panel is None:
        st.info(f"No {name} output available.")
        return

    cols = st.columns(2)
    with cols[0]:
        if original_image is not None:
            st.image(original_image, caption="Original", use_container_width=True)
    with cols[1]:
        st.image(panel["image"], caption=f"{name} overlay", use_container_width=True)

    st.markdown(
        f"<div class='fsd-mono' style='margin-top:8px;'>{legend}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='margin-top:12px;color:var(--text-secondary);'>"
        f"{panel['summary']}</div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Faithfulness", f"{panel['faithfulness']:.2f}")
    m2.metric("Localization (IoU)", f"{panel['localization_iou']:.2f}")
    m3.metric("Compute time", f"{panel['compute_ms']} ms")


def _all_panels_grid(xai_panels: dict, original_image):
    if not xai_panels:
        st.info("No XAI outputs available.")
        return
    cols = st.columns(4)
    cols[0].image(original_image, caption="Original", use_container_width=True)
    cols[1].image(xai_panels["gradcam"]["image"], caption="Grad-CAM++",
                  use_container_width=True)
    cols[2].image(xai_panels["shap"]["image"], caption="SHAP",
                  use_container_width=True)
    cols[3].image(xai_panels["lime"]["image"], caption="LIME",
                  use_container_width=True)

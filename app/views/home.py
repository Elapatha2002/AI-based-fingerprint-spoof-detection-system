"""Screen 1 — Home / Landing."""
import streamlit as st
from components.cards import feature_card


def render():
    st.markdown(
        """
        <div class="fsd-hero">
          <div class="fsd-hero-title">Explainable Fingerprint Spoof Detection<br/>
            <span style="color:var(--text-secondary);font-size:24px;">
              for Digital Forensics
            </span>
          </div>
          <div class="fsd-hero-sub">
            Detect silicone, gelatin, and latex spoofs with court-ready visual
            explanations powered by Grad-CAM++, SHAP, and LIME.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Symmetric layout: spacer | btn | btn | spacer  →  buttons are
    # truly centered and identical width regardless of label length.
    c1, c2, c3, c4 = st.columns([2.5, 1.4, 1.4, 2.5])
    with c2:
        if st.button("▶  Start Analysis",
                     type="primary",
                     use_container_width=True,
                     key="home_start"):
            st.session_state.current_page = "analyze"
            st.rerun()
    with c3:
        if st.button("📖  Methodology",
                     use_container_width=True,
                     key="home_methodology"):
            st.session_state.current_page = "about"
            st.rerun()

    st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

    cols = st.columns(3)
    with cols[0]:
        feature_card(
            "🛡",
            "Spoof Detection",
            "ResNet50V2 + CBAM attention. >95% AUC target on the LivDet 2013 "
            "benchmark with cross-dataset and cross-sensor evaluation.",
        )
    with cols[1]:
        feature_card(
            "🔬",
            "Forensic XAI",
            "Three explanation methods compared side-by-side: Grad-CAM++, "
            "SHAP, and LIME — with quantitative faithfulness scores.",
        )
    with cols[2]:
        feature_card(
            "📑",
            "Court-ready Reports",
            "PDF reports aligned to Daubert/Frye admissibility criteria, "
            "including model provenance and reproducibility metadata.",
        )

    st.markdown(
        "<div style='text-align:center;margin-top:32px;color:var(--text-muted);"
        "font-size:12px;'>Trained on LivDet 2013 · MSU-FPAD v2 · CrossMatch 300 · "
        "Biometrika 400B</div>",
        unsafe_allow_html=True,
    )

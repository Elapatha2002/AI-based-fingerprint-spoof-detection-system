"""Screen 1 — Home / Landing."""
import streamlit as st
from components.cards import feature_card


def render():
    st.markdown(
        """
        <section class="fsd-home-hero">
          <div class="fsd-home-eyebrow">Research decision-support workspace</div>
          <div class="fsd-home-title">Explainable fingerprint<br/>spoof detection</div>
          <div class="fsd-home-subtitle">
            Analyze a fingerprint, inspect the evidence behind the outcome,
            and prepare a traceable case record in one guided workflow.
          </div>
          <div class="fsd-home-proof">
            Human review remains essential: this research prototype supports,
            but does not replace, forensic judgement.
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    _, c_start, c_method, _ = st.columns([1.5, 1.4, 1.4, 1.5])
    with c_start:
        if st.button("Analyze a fingerprint",
                     type="primary",
                     width="stretch",
                     key="home_start"):
            st.session_state.current_page = "analyze"
            st.rerun()
    with c_method:
        if st.button("Review methodology",
                     width="stretch",
                     key="home_methodology"):
            st.session_state.current_page = "about"
            st.rerun()

    st.markdown("<div class='fsd-section-h'>How the workflow supports your case</div>",
                unsafe_allow_html=True)

    cols = st.columns(3)
    with cols[0]:
        feature_card(
            "01",
            "Analyze the sample",
            "Upload one fingerprint image or a batch archive, then record the "
            "case identifier, sensor, and contextual notes before processing.",
        )
    with cols[1]:
        feature_card(
            "02",
            "Review the evidence",
            "Compare the predicted outcome with Grad-CAM++, SHAP, and LIME "
            "visual explanations and their measured faithfulness indicators.",
        )
    with cols[2]:
        feature_card(
            "03",
            "Document the decision",
            "Save the analysis and generate a report containing the case "
            "context, model provenance, result, and explanatory images.",
        )

    st.markdown(
        "<div class='fsd-home-proof'>"
        "Training and methodological details, limitations, and model metrics are available in Methodology."
        "</div>",
        unsafe_allow_html=True,
    )

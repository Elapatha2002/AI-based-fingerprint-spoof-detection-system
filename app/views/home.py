"""Screen 1 — Home / Landing."""
import streamlit as st


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

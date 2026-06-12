"""Top navigation bar and bottom status bar."""
import streamlit as st

NAV_ITEMS = [
    ("home", "Home"),
    ("analyze", "Analyze"),
    ("history", "History"),
    ("about", "About"),
    ("compare_xai", "Compare"),
]


def render_nav():
    """Top nav with logo + nav links + version pill."""
    current = st.session_state.get("current_page", "home")

    cols = st.columns([1.2, 0.7, 0.8, 0.8, 0.7, 0.8, 4, 0.8])

    with cols[0]:
        if st.button("◼ FSD-XAI", key="nav_logo", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()

    for i, (page_key, label) in enumerate(NAV_ITEMS, start=1):
        with cols[i]:
            label_display = f"**{label}**" if current == page_key else label
            if st.button(label_display, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()

    with cols[7]:
        st.markdown(
            "<div style='text-align:right;color:#6E7681;font-family:ui-monospace,monospace;"
            "font-size:11px;padding-top:8px;'>v1.0.0</div>",
            unsafe_allow_html=True,
        )


def render_statusbar():
    """Bottom status bar with model + dataset provenance."""
    st.markdown(
        """
        <div class="fsd-status">
          Model: ResNet50V2-CBAM &nbsp;·&nbsp; Build a3f9b21 &nbsp;·&nbsp;
          LivDet 2013 &nbsp;·&nbsp; GPU: T4 &nbsp;·&nbsp; Mock predictions (UI prototype)
        </div>
        """,
        unsafe_allow_html=True,
    )

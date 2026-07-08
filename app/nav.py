"""Top navigation bar and bottom status bar."""
import os
import streamlit as st

NAV_ITEMS = [
    ("home", "Home"),
    ("analyze", "Analyze"),
    ("history", "History"),
    ("about", "About"),
    ("compare_xai", "Compare"),
]


def render_nav():
    """Top nav — link-style buttons CENTERED horizontally.

    Layout: [left spacer] [Home][Analyze][History][About][Compare] [right spacer]
    Version pill is fixed top-right via CSS, so centering remains symmetric
    regardless of viewport width.
    """
    # Fixed-position version pill (outside the column flow)
    st.markdown(
        "<div class='fsd-nav-version-pill'>v1.0.0</div>",
        unsafe_allow_html=True,
    )

    current = st.session_state.get("current_page", "home")

    # Symmetric: spacer | 5 nav buttons | spacer
    cols = st.columns([3, 0.8, 0.9, 0.85, 0.8, 0.9, 3])

    for i, (page_key, label) in enumerate(NAV_ITEMS, start=1):
        with cols[i]:
            label_display = f"**{label}**" if current == page_key else label
            if st.button(label_display,
                         key=f"nav_{page_key}",
                         use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()


def render_statusbar():
    """Bottom status bar v2 — chip-based, shows live model + thresholds + audit count.

    Auto-detects whether the app is in mock mode (default) or real mode
    (FSDXAI_REAL_MODEL=1). In real mode, the model + commit + device chips
    show the actual loaded checkpoint. Status bar is glanceable — every chip
    communicates a single piece of state.
    """
    chips: list[str] = []
    if os.environ.get("FSDXAI_REAL_MODEL") == "1":
        try:
            from services.real_model import get_service_info
            svc = get_service_info()
            chips.append(f"<span class='fsd-chip fsd-chip-info'>⚙ {svc['name']}</span>")
            chips.append(f"<span class='fsd-chip fsd-chip-muted'>commit {svc['commit']}</span>")
            chips.append(f"<span class='fsd-chip fsd-chip-muted'>{svc['device']}</span>")
            chips.append(
                "<span class='fsd-chip fsd-chip-success'>● LIVE inference</span>"
            )
        except Exception as e:
            chips.append(
                f"<span class='fsd-chip fsd-chip-spoof'>● real-model error</span>"
            )
            chips.append(
                f"<span class='fsd-chip fsd-chip-muted'>{type(e).__name__}</span>"
            )
    else:
        chips.append("<span class='fsd-chip fsd-chip-info'>⚙ mobilenetv3_large</span>")
        chips.append("<span class='fsd-chip fsd-chip-muted'>commit a3f9b21</span>")
        chips.append("<span class='fsd-chip fsd-chip-warn'>● MOCK predictions</span>")

    chips.append("<span class='fsd-status-spacer'></span>")

    # Threshold
    thr = st.session_state.get("decision_threshold", 0.5)
    chips.append(f"<span class='fsd-chip fsd-chip-muted'>threshold {thr:.2f}</span>")

    # Audit log count
    audit_count = len(st.session_state.get("audit_log", []))
    if audit_count:
        chips.append(
            f"<span class='fsd-chip fsd-chip-info'>📋 {audit_count} audit</span>"
        )
    else:
        chips.append("<span class='fsd-chip fsd-chip-muted'>📋 0 audit</span>")

    # Open-cases hint
    history = st.session_state.get("history", [])
    if history:
        chips.append(
            f"<span class='fsd-chip fsd-chip-muted'>"
            f"{len(history)} session entries</span>"
        )

    st.markdown(
        f"<div class='fsd-status'>{''.join(chips)}</div>",
        unsafe_allow_html=True,
    )

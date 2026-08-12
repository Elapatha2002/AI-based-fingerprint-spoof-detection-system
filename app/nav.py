"""Top navigation bar and bottom status bar."""
import os
import streamlit as st

# Base nav visible to every logged-in user
BASE_NAV = [
    ("home", "Home"),
    ("analyze", "Analyze"),
    ("history", "History"),
    ("about", "About"),
    ("compare_xai", "Compare"),
]

# Super-admin only nav
ADMIN_NAV = [
    ("settings", "Settings"),
]


def render_nav():
    """Top nav — link-style buttons CENTERED horizontally.

    Composition depends on the current user's role. The version pill sits
    fixed top-right; the sign-out control is rendered inline at the far
    right of the nav row.
    """
    # Fixed-position version pill
    st.markdown(
        "<div class='fsd-nav-version-pill'>v1.0.0</div>",
        unsafe_allow_html=True,
    )

    # Lazy import to avoid a circular dep with streamlit_app.py
    from app.services import auth
    user = auth.current_user()

    items = list(BASE_NAV)
    if user and user.get("role") == "super_admin":
        items = items + list(ADMIN_NAV)

    current = st.session_state.get("current_page", "home")

    # Symmetric layout: [left spacer] [nav items ...] [user/logout] [right spacer]
    n = len(items)
    # Slightly wider right column so full name + Sign out fit comfortably.
    ratios = [2] + [0.9] * n + [2.5] + [1.5]
    cols = st.columns(ratios)

    for i, (page_key, label) in enumerate(items, start=1):
        with cols[i]:
            label_display = f"**{label}**" if current == page_key else label
            if st.button(label_display,
                         key=f"nav_{page_key}",
                         use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()

    # User identity + sign out at the far right
    with cols[-2]:
        if user:
            role_label = ("Super Admin" if user["role"] == "super_admin"
                          else "Examiner")
            st.markdown(
                f"<div style='text-align:right;padding-top:6px;'>"
                f"<div style='font-size:13px;font-weight:600;color:var(--text-primary);'>"
                f"{user['full_name']}</div>"
                f"<div style='font-size:11px;color:var(--text-muted);'>"
                f"{role_label}</div></div>",
                unsafe_allow_html=True,
            )

    with cols[-1]:
        if user and st.button("Sign out", key="nav_signout",
                                use_container_width=True):
            auth.logout()
            st.session_state.current_page = "home"
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

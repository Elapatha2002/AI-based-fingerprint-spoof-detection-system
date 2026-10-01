"""Application navigation and a compact operational-status footer."""
from html import escape
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

# Detail pages belong to a navigation section, but are not navigation targets.
PAGE_SECTION = dict(single_result='analyze', processing='analyze',
                    batch_dashboard='analyze', drilldown='analyze',
                    report_preview='analyze', saved_analysis='history')


def _navigate(labels_to_pages):
    target = labels_to_pages.get(st.session_state.get('main_navigation'))
    if target:
        st.session_state.current_page = target
        st.session_state['_nav_synced_page'] = target


def render_nav():
    """Render a responsive, labelled application header and navigation.

    The former navigation used a set of narrow fractional columns.  It made
    labels wrap on ordinary laptop/desktop widths and left users without a
    clear product or account context.  ``st.pills`` provides a single,
    keyboard-operable navigation group whose selected state is explicit.
    """
    # Lazy import avoids a circular dependency with streamlit_app.py.
    from app.services import auth
    user = auth.current_user()

    items = list(BASE_NAV)
    if user and user.get("role") == "super_admin":
        items = items + list(ADMIN_NAV)
    elif user:
        items.append(('settings', 'My account'))

    current = st.session_state.get("current_page", "home")
    labels_to_pages = {label: page_key for page_key, label in items}
    active_label = next(
        (label for page_key, label in items
         if page_key == PAGE_SECTION.get(current, current)), None
    )

    # Product and account context are intentionally separated from the
    # navigation choices. It reduces scanning effort and prevents the account
    # controls from being mistaken for another page tab.
    brand_col, account_col = st.columns([3, 2])
    with brand_col:
        st.markdown(
            """
            <div class='fsd-app-brand'>
              <span class='fsd-brand-mark' aria-hidden='true'>F</span>
              <div>
                <div class='fsd-brand-name'>FSD-XAI</div>
                <div class='fsd-brand-context'>Forensic spoof detection workspace</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with account_col:
        if user:
            role_label = ("Super administrator" if user["role"] == "super_admin"
                          else "Forensic examiner")
            st.markdown(
                "<div class='fsd-account-summary'>"
                f"<span class='fsd-account-name'>{escape(user['full_name'])}</span>"
                f"<span class='fsd-account-role'>{role_label}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

    nav_col, signout_col = st.columns([5, 1])
    with nav_col:
        # Synchronise when navigation happens from a CTA elsewhere in the app,
        # but do not overwrite a user selection during the pills' change run.
        if st.session_state.get("_nav_synced_page") != current:
            st.session_state["main_navigation"] = active_label
            st.session_state["_nav_synced_page"] = current

        st.pills(
            "Primary navigation",
            list(labels_to_pages),
            selection_mode="single",
            key="main_navigation",
            label_visibility="collapsed",
            on_change=_navigate,
            args=(labels_to_pages,),
        )

    with signout_col:
        if user:
            st.button("Sign out", key="nav_signout", width="stretch",
                      on_click=auth.logout)


def render_statusbar():
    """Render a non-obstructive operational footer.

    This is deliberately in normal document flow instead of a fixed bar: a
    fixed status bar covered actions and competed with the case workflow.
    """
    chips: list[str] = []
    try:
        from app.services import auth, storage
        if auth.offline_mode_enabled():
            chips.append("<span class='fsd-chip fsd-chip-warn'>● LOCAL OFFLINE MODE</span>")
        elif isinstance(storage.get_storage(), storage.LocalStorageService):
            chips.append("<span class='fsd-chip fsd-chip-warn'>● LOCAL STORAGE</span>")
    except Exception:
        pass

    if os.environ.get("FSDXAI_REAL_MODEL") == "1":
        try:
            from services.real_model import get_service_info
            svc = get_service_info()
            chips.append(f"<span class='fsd-chip fsd-chip-info'>⚙ {svc['name']}</span>")
            chips.append(f"<span class='fsd-chip fsd-chip-muted'>commit {svc['commit']}</span>")
            chips.append(f"<span class='fsd-chip fsd-chip-muted'>{svc['device']}</span>")
            chips.append("<span class='fsd-chip fsd-chip-success'>● real model</span>")
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
        chips.append("<span class='fsd-chip fsd-chip-warn'>● demonstration model</span>")

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

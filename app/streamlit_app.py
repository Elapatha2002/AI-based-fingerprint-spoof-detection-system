"""
FSD-XAI — Streamlit entry point.

Run from the app/ folder:
    streamlit run streamlit_app.py
"""
import sys
from pathlib import Path

# Ensure local module imports work whether started from app/ or project root
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="FSD-XAI · Forensic Spoof Detection",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from theme import apply_theme  # noqa: E402
from state import init_state  # noqa: E402
from nav import render_nav, render_statusbar  # noqa: E402

from views import (  # noqa: E402
    home, analyze, processing, batch_dashboard,
    single_result, drilldown, report_preview,
    history, about, compare_xai, login, settings,
)

# Auth service — must import after sys.path is set up
from app.services import auth  # noqa: E402


PAGES = {
    "home": home.render,
    "analyze": analyze.render,
    "processing": processing.render,
    "batch_dashboard": batch_dashboard.render,
    "single_result": single_result.render,
    "drilldown": drilldown.render,
    "report_preview": report_preview.render,
    "history": history.render,
    "about": about.render,
    "compare_xai": compare_xai.render,
    "settings": settings.render,
}


# Bootstrap: seed super admin from .env if users table is empty.
# Runs once per process. Streamlit reruns the whole script on each event,
# so we guard with a module-level flag.
_BOOTSTRAP_DONE = False


def _bootstrap_once():
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    try:
        auth.seed_super_admin_if_needed()
    except Exception:
        pass
    _BOOTSTRAP_DONE = True


def main():
    apply_theme()
    init_state()
    _bootstrap_once()

    # AUTH GATE — if nobody is logged in, render only the login page.
    if not auth.is_logged_in():
        login.render()
        return

    render_nav()

    page_key = st.session_state.get("current_page", "home")

    # Role guard for admin-only pages
    if page_key == "settings" and not auth.is_super_admin():
        st.session_state.current_page = "home"
        page_key = "home"

    render_fn = PAGES.get(page_key, home.render)
    render_fn()

    render_statusbar()


if __name__ == "__main__":
    main()

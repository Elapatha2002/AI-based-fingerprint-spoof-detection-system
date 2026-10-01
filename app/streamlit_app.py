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

# Load the selected backend before view imports can load legacy .env values.
from dotenv import load_dotenv
load_dotenv(HERE.parent / '.env.supabase')
load_dotenv(HERE.parent / '.env')

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
    history, saved_analysis, about, compare_xai, login, settings,
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
    "saved_analysis": saved_analysis.render,
    "about": about.render,
    "compare_xai": compare_xai.render,
    "settings": settings.render,
}


def _bootstrap_once():
    # Supabase was provisioned by the wizard. Login validates connectivity;
    # do not open another cloud connection just to inspect the schema on clicks.
    if auth.database.using_postgres():
        return
    if st.session_state.get('_local_db_ready'):
        return
    try:
        auth.database.init_db()
        auth.seed_super_admin_if_needed()
    except Exception:
        return  # Retry on the next interaction if local setup failed.
    st.session_state['_local_db_ready'] = True


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

    # Settings renders only My account for examiners; mutations recheck roles.

    render_fn = PAGES.get(page_key, home.render)
    render_fn()

    render_statusbar()


if __name__ == "__main__":
    with auth.render_scope():
        main()

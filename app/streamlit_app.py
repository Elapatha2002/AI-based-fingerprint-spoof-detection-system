"""
FSD-XAI — Streamlit entry point.

Run from the project root (recommended):
    python -m streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

# Streamlit Cloud executes the selected file with its own script directory on
# sys.path, but that does not make the parent ``app`` package importable.  Keep
# both paths explicit because the application still contains a mixture of
# package imports (``app.services``) and legacy top-level imports (``views``,
# ``components`` and ``services``).
HERE = Path(__file__).parent.resolve()
PROJECT_ROOT = HERE.parent
for import_root in (PROJECT_ROOT, HERE):
    import_path = str(import_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

# Load the selected backend before view imports can load legacy .env values.
from dotenv import load_dotenv
load_dotenv(HERE.parent / '.env.supabase')
load_dotenv(HERE.parent / '.env')

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="FSD-XAI · Forensic Spoof Detection",
    page_icon=str(HERE / "static" / "brand" / "fsd-xai-logo.png"),
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

    # AUTH GATE — restore a signed browser session after a full refresh. A
    # successful form submission continues into Home in this same execution,
    # avoiding a second loading/rerun transition.
    user = auth.current_user()
    if not user:
        if not login.render():
            auth.render_session_cookie(None)
            return
        init_state()  # login clears the previous examiner's transient state
        user = auth.current_user()

    auth.render_session_cookie(user)

    render_nav()

    page_key = st.session_state.get("current_page", "home")

    # Settings renders only My account for examiners; mutations recheck roles.

    render_fn = PAGES.get(page_key, home.render)
    render_fn()

    render_statusbar()


if __name__ == "__main__":
    with auth.render_scope():
        main()

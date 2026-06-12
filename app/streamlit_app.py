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
    history, about, compare_xai,
)


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
}


def main():
    apply_theme()
    init_state()
    render_nav()

    page_key = st.session_state.get("current_page", "home")
    render_fn = PAGES.get(page_key, home.render)
    render_fn()

    render_statusbar()


if __name__ == "__main__":
    main()

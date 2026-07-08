"""Session state initialization and helpers."""
import streamlit as st
from datetime import datetime


def init_state():
    """Initialize session state on first load. Idempotent."""
    defaults = {
        "current_page": "home",
        "history": [],
        "current_batch": None,
        "current_single": None,
        "drilldown_idx": 0,
        "current_report_target": None,
        "form_case_id": "",
        "form_examiner": "",
        "form_sensor": "Biometrika 400B",
        "form_notes": "",
        # New for v2 UI
        "audit_log": [],            # list of {ts, actor, action, case_id, details}
        "decision_threshold": 0.5,  # configurable classifier threshold
        "eer_threshold": 0.22,      # operating point from thesis evaluation
        "case_status": "Open",      # Open | In Review | Closed | Escalated
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def goto(page: str, **kwargs):
    """Navigate to a page, optionally setting state keys."""
    st.session_state.current_page = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()


def add_to_history(entry: dict):
    """Persist an analysis (single or batch) to session history."""
    entry.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    st.session_state.history.insert(0, entry)


def auto_case_id() -> str:
    """Generate a default case ID using current date + entropy from history length."""
    today = datetime.now().strftime("%Y")
    seq = len(st.session_state.get("history", [])) + 1
    return f"CASE-{today}-{seq:04d}"

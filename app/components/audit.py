"""Append-only audit log + drawer renderer.

Every action that touches case state should append an entry via log_action().
The log is visible in the audit drawer (expander) on result + report pages,
and a summary appears in the status bar.
"""
from datetime import datetime
import streamlit as st


# ─────────────────────────────────────────────────────────────────────
# Logging API
# ─────────────────────────────────────────────────────────────────────

def log_action(action: str,
               case_id: str = "—",
               actor: str | None = None,
               details: str = "") -> None:
    """Append an entry to st.session_state.audit_log.

    Args:
        action:  short verb phrase ("uploaded image", "classified", ...)
        case_id: case identifier
        actor:   who did it (defaults to current examiner if set)
        details: free-form additional info shown after the action verb
    """
    # The analysis form displays the authenticated account, not form_examiner.
    # Do not attribute an action to a stale name left by a previous session.
    from app.services import auth
    user = auth.current_user() or {}
    actor = actor or user.get("full_name") or user.get("username") or "Unattributed"
    # Session validation can revoke and clear a disabled account's state.
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []

    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "actor": actor,
        "action": action,
        "case_id": case_id,
        "details": details,
    }
    st.session_state.audit_log.append(entry)

    # Best-effort dual write to the database so the audit trail survives restarts.
    # A DB outage must not break the UI, so all failures are swallowed.
    try:
        from app.services import database
        db_case_id = "" if case_id in ("—", "-") else case_id
        database.log_event(action=action, case_id=db_case_id,
                            user=actor, details=details)
    except Exception:
        pass


def log_count() -> int:
    return len(st.session_state.get("audit_log", []))


def latest_entry() -> dict | None:
    log = st.session_state.get("audit_log", [])
    return log[-1] if log else None


# ─────────────────────────────────────────────────────────────────────
# Drawer renderer
# ─────────────────────────────────────────────────────────────────────

def render_audit_drawer(case_id: str | None = None,
                        title: str = "Audit log",
                        expanded: bool = False) -> None:
    """Drop into any page to show the action history for a case.

    If case_id is given, only entries for that case are shown.
    """
    log = list(st.session_state.get("audit_log", []))
    if case_id:
        log = [e for e in log if e.get("case_id") == case_id]

    count = len(log)
    badge = f" ({count})" if count else ""

    with st.expander(f"📋  {title}{badge}", expanded=expanded):
        if not log:
            st.markdown(
                "<div style='color:var(--text-muted);font-size:12px;"
                "padding:8px 0;'>No actions logged yet.</div>",
                unsafe_allow_html=True,
            )
            return

        rows_html = []
        for e in reversed(log):                     # newest first
            ts_display = e["ts"][:19].replace("T", " ")
            action_text = e["action"]
            if e.get("details"):
                action_text += (
                    f"&nbsp;&nbsp;<span style='color:var(--text-muted);'>"
                    f"· {e['details']}</span>"
                )
            rows_html.append(
                f"<div class='fsd-audit-row'>"
                f"<span class='fsd-audit-ts'>{ts_display}</span>"
                f"<span class='fsd-audit-actor'>{e['actor']}</span>"
                f"<span class='fsd-audit-action'>{action_text}</span>"
                f"</div>"
            )

        st.markdown(
            f"<div class='fsd-audit-log'>{''.join(rows_html)}</div>",
            unsafe_allow_html=True,
        )

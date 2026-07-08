"""Persistent case-context strip rendered at the top of result / drilldown /
report / batch-dashboard pages. Mirrors the look of enterprise forensic
platforms — Case ID is the primary anchor, status + examiner give context
at a glance."""
import streamlit as st


STATUS_COLORS = {
    "Open":       "#58A6FF",
    "In Review":  "#D29922",
    "Closed":     "#3FB950",
    "Escalated":  "#F85149",
}


def render_case_strip(meta: dict,
                     status: str | None = None,
                     extra_right: str = "") -> None:
    """Render the case-context strip.

    Args:
        meta:        dict with case_id, examiner, sensor, optional timestamp
        status:      one of Open / In Review / Closed / Escalated
                     (defaults to session-state case_status)
        extra_right: optional HTML fragment shown right-aligned (e.g. counts)
    """
    status = status or st.session_state.get("case_status", "Open")
    color = STATUS_COLORS.get(status, "#8B949E")

    case_id = meta.get("case_id", "—")
    examiner = meta.get("examiner", "—")
    sensor = meta.get("sensor", "—")
    ts = (meta.get("timestamp") or "")[:16] or "—"

    right_html = ""
    if extra_right:
        right_html = (
            f"<div class='fsd-case-meta' style='text-align:right;'>"
            f"{extra_right}</div>"
        )

    st.markdown(
        f"""
        <div class='fsd-case-strip'>
          <div class='fsd-case-id'>◈ {case_id}</div>
          <div class='fsd-case-divider'></div>
          <div class='fsd-case-meta'>
            <span class='fsd-case-label'>Status</span>
            <span class='fsd-case-value' style='color:{color}'>● {status}</span>
          </div>
          <div class='fsd-case-meta'>
            <span class='fsd-case-label'>Examiner</span>
            <span class='fsd-case-value'>{examiner}</span>
          </div>
          <div class='fsd-case-meta'>
            <span class='fsd-case-label'>Sensor</span>
            <span class='fsd-case-value'>{sensor}</span>
          </div>
          <div class='fsd-case-meta-spacer'></div>
          <div class='fsd-case-meta' style='text-align:right;'>
            <span class='fsd-case-label'>Last Action</span>
            <span class='fsd-case-value'>{ts}</span>
          </div>
          {right_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

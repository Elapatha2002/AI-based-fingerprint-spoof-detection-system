"""
Fingerprint Matcher Demo — standalone.

Runs independently of the main FSD-XAI system. Purpose: demonstrate that
a plain fingerprint matcher accepts a spoofed fingerprint as if it were
the real user, motivating the need for the XAI-based spoof detector.

Run from the project root:

    streamlit run demo_matcher/streamlit_app.py

Three tabs:

    Enrol       — auto-assign a User ID, capture a fingerprint, save.
    Identify    — capture a fingerprint, return the matched user + score.
    Directory   — browse, delete, or clear enrolled users.

The sensor is the shared Mantra MFS100 abstraction in
app/services/mantra_sensor.py. The UI never distinguishes between real
and emulated capture — both paths return the same MantraCaptureResult
and the app behaves identically. Once the physical sensor is connected
and MANTRA_SENSOR_MODE=real is set in .env, captures switch over with
no UI change.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.mantra_sensor import (
    capture_fingerprint, is_available, MantraSensorError,
)
from demo_matcher import matcher


# ── Page setup ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Fingerprint Matcher",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)


CSS = """
<style>
    .fmd-hero {
        padding: 24px 0 4px 0;
    }
    .fmd-hero-title {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .fmd-hero-sub {
        color: #94a3b8;
        font-size: 14px;
        margin-top: 4px;
    }
    .fmd-status {
        text-align: right;
        padding-top: 34px;
    }
    .fmd-status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
    }
    .fmd-status-ready   { background: #22c55e; box-shadow: 0 0 8px #22c55e66; }
    .fmd-status-offline { background: #ef4444; box-shadow: 0 0 8px #ef444466; }
    .fmd-status-label {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
        color: #cbd5e1;
        vertical-align: middle;
    }
    .fmd-panel {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 24px;
        margin-top: 8px;
    }
    .fmd-panel-title {
        font-size: 12px;
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
    .fmd-user-id-chip {
        display: inline-block;
        padding: 8px 14px;
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 15px;
        font-weight: 600;
        color: #93c5fd;
    }
    .fmd-user-id-label {
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 6px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .fmd-placeholder {
        background: rgba(255,255,255,0.02);
        border: 1.5px dashed rgba(255,255,255,0.12);
        border-radius: 12px;
        padding: 60px 30px;
        text-align: center;
        color: #64748b;
    }
    .fmd-placeholder-icon {
        font-size: 44px;
        margin-bottom: 12px;
        opacity: 0.7;
    }
    .fmd-placeholder-title {
        font-size: 15px;
        font-weight: 600;
        color: #94a3b8;
        margin-bottom: 6px;
    }
    .fmd-placeholder-sub {
        font-size: 12px;
        color: #64748b;
    }
    .fmd-verdict-match {
        background: linear-gradient(135deg, #14532d 0%, #166534 100%);
        border-left: 4px solid #22c55e;
        padding: 24px 28px;
        border-radius: 10px;
    }
    .fmd-verdict-nomatch {
        background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
        border-left: 4px solid #ef4444;
        padding: 24px 28px;
        border-radius: 10px;
    }
    .fmd-verdict-kicker {
        font-size: 11px;
        letter-spacing: 0.12em;
        color: rgba(255,255,255,0.7);
        text-transform: uppercase;
        font-weight: 600;
    }
    .fmd-verdict-name {
        font-size: 26px;
        font-weight: 700;
        color: #ffffff;
        margin: 6px 0 10px 0;
    }
    .fmd-verdict-meta {
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
        color: rgba(255,255,255,0.85);
    }
</style>
"""


def _header():
    st.markdown(CSS, unsafe_allow_html=True)
    cols = st.columns([3, 1])
    with cols[0]:
        st.markdown(
            """
            <div class='fmd-hero'>
              <div class='fmd-hero-title'>🔎 Fingerprint Matcher</div>
              <div class='fmd-hero-sub'>
                1-to-N fingerprint identification system.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        _sensor_status()


def _sensor_status():
    """Show sensor connectivity WITHOUT revealing implementation mode."""
    ok, _ = is_available()
    dot_class = "fmd-status-ready" if ok else "fmd-status-offline"
    label = "Sensor ready" if ok else "Sensor not detected"
    st.markdown(
        f"""
        <div class='fmd-status'>
          <span class='fmd-status-dot {dot_class}'></span>
          <span class='fmd-status-label'>{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    _header()

    tab_enrol, tab_match, tab_directory = st.tabs(
        ["  Enroll  ", "  Identify  ", "  Directory  "]
    )

    with tab_enrol:
        _render_enrol_tab()

    with tab_match:
        _render_match_tab()

    with tab_directory:
        _render_directory_tab()


# ── Enrol ────────────────────────────────────────────────────────────

def _render_enrol_tab():
    # Layout: 5/6 - form on left, capture preview on right
    cols = st.columns([1, 1.05], gap="large")

    with cols[0]:
        st.markdown('<div class="fmd-panel-title">New enrolment</div>',
                    unsafe_allow_html=True)

        # Auto-generated User ID — displayed as a chip, not an input
        auto_id = matcher.next_user_id()
        st.markdown(
            f'<div class="fmd-user-id-label">Assigned user ID</div>'
            f'<div class="fmd-user-id-chip">{auto_id}</div>'
            f'<div style="height:20px;"></div>',
            unsafe_allow_html=True,
        )

        display_name = st.text_input(
            "Full name",
            placeholder="e.g. Daemon Tagerion",
            key="enrol_name",
        )
        finger_label = st.selectbox(
            "Finger being enrolled",
            ["Right index", "Left index", "Right thumb", "Left thumb",
             "Right middle", "Left middle"],
            key="enrol_finger",
        )

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        # Two-step commit — capture, then save. Prevents accidental saves.
        capture_col, save_col = st.columns([1, 1])
        with capture_col:
            capture_clicked = st.button(
                "🖐  Capture",
                type="primary",
                use_container_width=True,
                key="enrol_capture",
                disabled=not display_name.strip(),
            )
        with save_col:
            has_capture = bool(st.session_state.get("enrol_last_capture"))
            save_clicked = st.button(
                "💾  Save enrolment",
                type="secondary",
                use_container_width=True,
                key="enrol_save",
                disabled=(not has_capture) or (not display_name.strip()),
            )

        if not display_name.strip():
            st.caption("Enter a full name to enable capture.")

    with cols[1]:
        st.markdown('<div class="fmd-panel-title">Fingerprint preview</div>',
                    unsafe_allow_html=True)
        _render_capture_preview_slot("enrol_last_capture")

    # ── Handle actions ──
    if capture_clicked:
        _do_capture(store_key="enrol_last_capture")
        st.rerun()

    if save_clicked:
        try:
            capture = st.session_state["enrol_last_capture"]
            e = matcher.enrol(
                user_id=auto_id,
                display_name=display_name.strip(),
                image_bytes=capture.image_bytes,
                finger_label=finger_label,
            )
            st.session_state["enrol_last_capture"] = None
            st.success(
                f"✓ Enrolled {e.display_name} as {e.user_id}. "
                f"{matcher.count_enrolled()} user{'s' if matcher.count_enrolled() != 1 else ''} in directory."
            )
        except Exception as e:
            st.error(f"Enrolment failed: {e}")


# ── Identify (match) ────────────────────────────────────────────────

def _render_match_tab():
    if matcher.count_enrolled() == 0:
        st.markdown(
            """
            <div class='fmd-placeholder' style='margin-top:16px;'>
              <div class='fmd-placeholder-icon'>👥</div>
              <div class='fmd-placeholder-title'>Directory is empty</div>
              <div class='fmd-placeholder-sub'>
                Enrol at least one user before running identification.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    cols = st.columns([1, 1.05], gap="large")

    with cols[0]:
        st.markdown('<div class="fmd-panel-title">Identification</div>',
                    unsafe_allow_html=True)
        st.markdown(
            f"<div style='color:#94a3b8;font-size:13px;margin-bottom:14px;'>"
            f"Place a finger on the sensor and press Capture. The captured "
            f"fingerprint will be compared against every enrolled user ",
            unsafe_allow_html=True,
        )

        capture_clicked = st.button(
            "🖐  Capture and identify",
            type="primary",
            use_container_width=True,
            key="match_capture",
        )

    with cols[1]:
        st.markdown('<div class="fmd-panel-title">Fingerprint preview</div>',
                    unsafe_allow_html=True)
        _render_capture_preview_slot("match_last_capture")

    if capture_clicked:
        try:
            with st.spinner("Waiting for finger on sensor..."):
                capture = capture_fingerprint()
            st.session_state["match_last_capture"] = capture
            st.session_state["match_last_result"] = matcher.match(capture.image_bytes)
        except MantraSensorError as e:
            st.error(f"Sensor error: {e}")
        st.rerun()

    result = st.session_state.get("match_last_result")
    if result is not None:
        st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
        _render_match_verdict(result)


def _render_match_verdict(result):
    if result.matched:
        st.markdown(
            f"""
            <div class='fmd-verdict-match'>
              <div class='fmd-verdict-kicker'>Match found</div>
              <div class='fmd-verdict-name'>Welcome, {result.display_name}</div>
              <div class='fmd-verdict-meta'>
                user_id = {result.user_id}
                &nbsp;·&nbsp; similarity = {result.score:.3f}
                &nbsp;·&nbsp; threshold = {result.threshold:.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class='fmd-verdict-nomatch'>
              <div class='fmd-verdict-kicker'>No match</div>
              <div class='fmd-verdict-name'>Access denied</div>
              <div class='fmd-verdict-meta'>
                highest similarity = {result.score:.3f}
                &nbsp;·&nbsp; threshold = {result.threshold:.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Similarity against every enrolled user"):
        for uid, score in result.ranked:
            bar_length = int(max(0, min(1, score)) * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            colour = "#22c55e" if score >= result.threshold else "#94a3b8"
            st.markdown(
                f"<div style='font-family:ui-monospace,monospace;font-size:13px;"
                f"color:{colour};padding:4px 0;'>"
                f"{uid:<12s}  {score:+.3f}  {bar}"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Directory ───────────────────────────────────────────────────────

def _render_directory_tab():
    enrolments = matcher.list_enrolments()
    if not enrolments:
        st.markdown(
            """
            <div class='fmd-placeholder' style='margin-top:16px;'>
              <div class='fmd-placeholder-icon'>📇</div>
              <div class='fmd-placeholder-title'>No users enrolled yet</div>
              <div class='fmd-placeholder-sub'>
                Head to the Enrol tab to add the first user.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<div style='color:#94a3b8;font-size:13px;margin:12px 0 20px 0;'>"
        f"{len(enrolments)} enrolled user{'s' if len(enrolments) != 1 else ''} "
        f"in the directory.</div>",
        unsafe_allow_html=True,
    )

    for e in enrolments:
        with st.container(border=True):
            cols = st.columns([2, 2, 2, 1])
            with cols[0]:
                st.markdown(
                    f"<div style='font-weight:600;font-size:15px;'>"
                    f"{e.display_name}</div>"
                    f"<div style='font-family:ui-monospace,monospace;"
                    f"color:#94a3b8;font-size:12px;'>{e.user_id}</div>",
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f"<div style='font-size:11px;color:#94a3b8;letter-spacing:0.06em;"
                    f"text-transform:uppercase;'>Finger</div>"
                    f"<div style='font-size:14px;'>{e.finger_label}</div>",
                    unsafe_allow_html=True,
                )
            with cols[2]:
                st.markdown(
                    f"<div style='font-size:11px;color:#94a3b8;letter-spacing:0.06em;"
                    f"text-transform:uppercase;'>Enrolled at</div>"
                    f"<div style='font-family:ui-monospace,monospace;font-size:12px;'>"
                    f"{e.enrolled_at.replace('T', ' ')}</div>",
                    unsafe_allow_html=True,
                )
            with cols[3]:
                if st.button("Remove", key=f"del_{e.user_id}",
                              use_container_width=True):
                    matcher.delete_enrolment(e.user_id)
                    st.rerun()

    st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
    with st.expander("Danger zone"):
        st.caption(
            "Removes every enrolled user. Cannot be undone. "
            "Only use when preparing a fresh demo."
        )
        if st.button("🗑  Clear entire directory", type="secondary"):
            n = matcher.clear_all()
            st.warning(f"Removed {n} enrolments.")
            st.rerun()


# ── Shared helpers ──────────────────────────────────────────────────

def _do_capture(store_key: str) -> None:
    """Capture from the sensor and stash in session state under store_key."""
    try:
        with st.spinner("Waiting for finger on sensor..."):
            capture = capture_fingerprint()
        st.session_state[store_key] = capture
    except MantraSensorError as e:
        st.error(f"Sensor error: {e}")


def _render_capture_preview_slot(state_key: str) -> None:
    """Show the captured fingerprint if present, else a placeholder card."""
    capture = st.session_state.get(state_key)
    if capture is None:
        st.markdown(
            """
            <div class='fmd-placeholder'>
              <div class='fmd-placeholder-icon'>👆</div>
              <div class='fmd-placeholder-title'>Awaiting capture</div>
              <div class='fmd-placeholder-sub'>
                The fingerprint image will appear here after you press Capture.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    img = capture.pil_image()
    st.image(img, use_container_width=True)
    st.markdown(
        f"<div style='font-family:ui-monospace,monospace;font-size:11px;"
        f"color:#94a3b8;padding-top:6px;text-align:center;'>"
        f"{capture.width}×{capture.height} px  ·  {capture.dpi} DPI"
        f"  ·  quality {capture.quality if capture.quality is not None else '—'}"
        f"</div>",
        unsafe_allow_html=True,
    )


render()

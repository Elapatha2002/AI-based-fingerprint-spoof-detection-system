"""Screen 2 — Analyze (single + batch zip upload)."""
import base64
from io import BytesIO

import streamlit as st
from components.cards import page_title, banner
from components.audit import log_action
from utils.image_loader import load_image, is_supported
from utils.zip_handler import inspect_zip
from state import auto_case_id


SENSORS = [
    "Biometrika 400B",
    "CrossMatch 300",
    "Digital Persona U.are.U",
    "Mantra MFS100",
    "Other",
    "Unknown",
]


def _start_single(meta):
    """Button callback: prepare the result before the next page render."""
    from app.services import auth
    with auth.render_scope():
        user = auth.current_user()
        data = st.session_state.get('single_source_bytes')
        if not user or not data or not meta.get('case_id'):
            return
        meta = dict(meta, examiner=user['full_name'])
        filename = st.session_state.get('single_source_filename') or 'capture.png'
        st.session_state.current_single = dict(filename=filename, image_bytes=data, meta=meta)
        log_action(action=f'Started analysis of {filename}', case_id=meta['case_id'],
                   details=f"sensor={meta.get('sensor')}, source={st.session_state.get('single_source_kind')}")
        st.session_state.current_page = 'single_result'


def render():
    page_title("Analyze Fingerprint",
               "Follow the guided steps to prepare a single fingerprint or a batch for analysis.")

    tab_single, tab_batch = st.tabs(["Single Image", "Batch (.zip)"])

    with tab_single:
        _render_single_tab()

    with tab_batch:
        _render_batch_tab()


def _render_meta_form(key_prefix: str):
    """Shared case metadata form. Returns dict of values.

    The examiner field is auto-filled from the logged-in user and rendered
    read-only. The case ID is auto-incremented from the DB.
    """
    if not st.session_state.get("form_case_id"):
        st.session_state.form_case_id = auto_case_id()

    # Pull the examiner from the auth session
    from app.services import auth
    user = auth.current_user()
    examiner_name = user["full_name"] if user else ""

    case_id = st.text_input(
        "Case ID *",
        value=st.session_state.form_case_id,
        key=f"{key_prefix}_case_id",
        help="Auto-incremented per year. Format: CASE-YYYY-####",
    )
    st.text_input(
        "Examiner (from your account)",
        value=examiner_name,
        key=f"{key_prefix}_examiner_display",
        disabled=True,
        help="This field is set by your login account and cannot be edited.",
    )
    sensor = st.selectbox(
        "Sensor",
        SENSORS,
        index=SENSORS.index(st.session_state.form_sensor)
        if st.session_state.form_sensor in SENSORS else 0,
        key=f"{key_prefix}_sensor",
    )
    notes = st.text_area(
        "Notes (optional)",
        value=st.session_state.form_notes,
        key=f"{key_prefix}_notes",
        max_chars=500,
        height=100,
    )

    return {
        "case_id": case_id.strip(),
        "examiner": examiner_name.strip(),
        "sensor": sensor,
        "notes": notes.strip(),
    }


def _render_single_tab():
    cols = st.columns([1.4, 1])

    with cols[0]:
        st.markdown("<div class='fsd-section-h'>Step 1 · Select an input</div>",
                    unsafe_allow_html=True)
        # Source selector — file upload OR live sensor capture. Both paths
        # populate the same session_state["single_source_bytes"] / filename
        # so the Start Analysis button downstream doesn't care which was used.
        source = st.radio(
            "Input method",
            ["Upload an image file", "Capture from Mantra sensor"],
            horizontal=True,
            key="single_source",
        )

        previous_source = st.session_state.get("_single_source_selection")
        if previous_source != source:
            st.session_state["single_source_bytes"] = None
            st.session_state["single_source_filename"] = None
            st.session_state["single_source_kind"] = None
            st.session_state["single_last_capture_info"] = None
            st.session_state["_single_source_selection"] = source

        if source.startswith("Upload"):
            _render_file_uploader()
        else:
            # Keep forensic metadata consistent with the actual capture source.
            st.session_state.form_sensor = "Mantra MFS100"
            st.session_state["single_sensor"] = "Mantra MFS100"
            _render_sensor_capture()

    with cols[1]:
        st.markdown(
            "<div class='fsd-section-h'>Step 2 · Case details</div>",
            unsafe_allow_html=True,
        )
        meta = _render_meta_form("single")

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # Ready if EITHER source provided image bytes + case_id + examiner
        source_bytes = st.session_state.get("single_source_bytes")
        ready = (bool(source_bytes)
                 and bool(meta["case_id"])
                 and bool(meta["examiner"]))

        st.markdown("<div class='fsd-section-h'>Step 3 · Run analysis</div>",
                    unsafe_allow_html=True)
        if not ready:
            st.caption("Add a valid fingerprint image and a case ID to continue.")

        st.button("Run analysis",
                     type="primary",
                     disabled=not ready,
                     width="stretch",
                     key="single_start", on_click=_start_single, args=(meta,))


def _render_file_uploader():
    """File-upload source. Populates single_source_bytes and _filename."""
    st.markdown(
        "<div class='fsd-section-h'>Fingerprint image</div>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "Drop an image here or browse your device",
        type=["png", "jpg", "jpeg", "bmp", "tif", "tiff"],
        accept_multiple_files=False,
        key="single_uploader",
    )
    st.markdown(
        "<div class='fsd-upload-guidance'><strong>Accepted:</strong> PNG, JPG, JPEG, "
        "BMP, TIF, and TIFF. <strong>Limit:</strong> 10 MB and 50–4096 px. "
        "The image stays associated with this case.</div>",
        unsafe_allow_html=True,
    )

    if uploaded is not None:
        uploaded.seek(0)
        img, err = load_image(uploaded)
        if err:
            banner(err, kind="error")
            st.session_state["single_source_bytes"] = None
            return
        uploaded.seek(0)
        image_bytes = uploaded.read()

        st.image(img,
                 caption=f"{uploaded.name} · {img.size[0]}×{img.size[1]} px",
                 width="stretch")

        st.session_state["single_source_bytes"] = image_bytes
        st.session_state["single_source_filename"] = uploaded.name
        st.session_state["single_source_kind"] = "file_upload"
    else:
        # Clear stale bytes if the user removed the file
        if st.session_state.get("single_source_kind") == "file_upload":
            st.session_state["single_source_bytes"] = None
            st.session_state["single_source_filename"] = None


def _render_sensor_capture():
    """Live-sensor source. Populates single_source_bytes and _filename."""
    from app.services.mantra_sensor import (
        bridge_url, capture_fingerprint, capture_transport, current_mode,
        is_available, MantraSensorError,
    )

    st.markdown(
        "<div class='fsd-section-h'>Capture from Mantra MFS100</div>",
        unsafe_allow_html=True,
    )

    # With hosted Streamlit, this component executes the request in the user's
    # browser so 127.0.0.1 means the examiner's PC, not the cloud server.
    if current_mode() == "real" and capture_transport() == "bridge":
        from components.mantra_capture import render_mantra_capture
        payload = render_mantra_capture(bridge_url=bridge_url())
        if payload and payload.get("ok"):
            capture_id = payload.get("capture_id")
            if capture_id and capture_id != st.session_state.get("single_capture_id"):
                try:
                    image_bytes = base64.b64decode(payload["image_base64"], validate=True)
                    img, err = load_image(BytesIO(image_bytes))
                    if err or img is None:
                        raise ValueError(err or "Invalid image")
                    captured_at = payload.get("captured_at", "capture")
                    filename = f"mantra_{captured_at.replace(':', '-')}.png"
                    st.session_state["single_source_bytes"] = image_bytes
                    st.session_state["single_source_filename"] = filename
                    st.session_state["single_source_kind"] = "sensor_capture"
                    st.session_state["single_capture_id"] = capture_id
                    st.session_state["single_last_capture_info"] = {
                        "width": int(payload.get("width") or img.width),
                        "height": int(payload.get("height") or img.height),
                        "dpi": int(payload.get("dpi") or 500),
                        "quality": payload.get("quality"),
                        "nfiq": payload.get("nfiq"),
                        "serial": payload.get("serial"),
                        "captured_at": captured_at,
                    }
                except (KeyError, ValueError, TypeError) as exc:
                    banner(f"Capture failed: the local bridge returned an invalid image ({exc}).",
                           kind="error")
        _render_last_sensor_capture()
        return

    ok, status_message = is_available()
    if ok:
        st.markdown(
            "<div class='fsd-mono' style='font-size:12px;margin-bottom:12px;'>"
            "<span style='color:var(--accent-live);'>● Sensor ready</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(status_message)
    else:
        st.markdown(
            "<div class='fsd-mono' style='font-size:12px;margin-bottom:12px;'>"
            "<span style='color:var(--accent-spoof);'>● Sensor not detected</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        banner(
            status_message,
            kind="warn",
        )
        return

    if st.button("Capture fingerprint",
                  type="primary",
                  width="stretch",
                  key="single_capture_btn"):
        try:
            with st.spinner("Waiting for finger on sensor..."):
                result = capture_fingerprint(timeout_seconds=20)

            filename = f"sensor_{result.captured_at.replace(':', '-')}.png"
            st.session_state["single_source_bytes"] = result.image_bytes
            st.session_state["single_source_filename"] = filename
            st.session_state["single_source_kind"] = "sensor_capture"
            st.session_state["single_last_capture_info"] = {
                "width": result.width,
                "height": result.height,
                "dpi": result.dpi,
                "quality": result.quality,
                "serial": result.device_serial,
                "captured_at": result.captured_at,
            }
        except MantraSensorError as e:
            banner(f"Capture failed: {e}", kind="error")

    _render_last_sensor_capture()


def _render_last_sensor_capture():
    if (st.session_state.get("single_source_kind") != "sensor_capture"
            or not st.session_state.get("single_source_bytes")):
        return
    from PIL import Image
    img = Image.open(BytesIO(st.session_state["single_source_bytes"]))
    info = st.session_state.get("single_last_capture_info", {}) or {}
    details = [
        f"{info.get('width', '?')}×{info.get('height', '?')} px",
        f"{info.get('dpi', '?')} DPI",
        f"quality {info.get('quality') if info.get('quality') is not None else 'not reported'}",
    ]
    if info.get("nfiq") is not None:
        details.append(f"NFIQ {info['nfiq']}")
    st.image(img, caption=" · ".join(details), width=320)


def _render_batch_tab():
    cols = st.columns([1.4, 1])

    with cols[0]:
        st.markdown(
            "<div class='fsd-section-h'>Step 1 · Upload a batch archive</div>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Drop a ZIP archive here or browse your device",
            type=["zip"],
            accept_multiple_files=False,
            key="batch_uploader",
        )
        st.markdown(
            "<div class='fsd-upload-guidance'><strong>Accepted:</strong> ZIP archives "
            "containing PNG, JPG, JPEG, BMP, TIF, or TIFF images. Subfolders are allowed. "
            "<strong>Archive limit:</strong> 50 MB.</div>",
            unsafe_allow_html=True,
        )

        summary = None
        if uploaded is not None:
            summary = inspect_zip(uploaded)
            if summary["errors"]:
                for e in summary["errors"]:
                    banner(e, kind="error")
            elif summary["valid"] == 0:
                banner("No supported images found in this zip.", kind="warn")
            else:
                msg = (
                    f"<b>{uploaded.name}</b> &nbsp;·&nbsp; "
                    f"{summary['valid']} images "
                )
                if summary["ignored"]:
                    msg += f"<span class='fsd-pill muted'>{summary['ignored']} ignored</span>"
                banner(msg, kind="info")

    with cols[1]:
        st.markdown(
            "<div class='fsd-section-h'>Step 2 · Case details</div>",
            unsafe_allow_html=True,
        )
        meta = _render_meta_form("batch")
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        valid_count = summary["valid"] if summary else 0
        ready = (uploaded is not None
                 and valid_count > 0
                 and meta["case_id"]
                 and meta["examiner"])

        btn_label = (f"Run batch analysis ({valid_count} images)"
                     if valid_count else "Run batch analysis")

        st.markdown("<div class='fsd-section-h'>Step 3 · Run analysis</div>",
                    unsafe_allow_html=True)
        if not ready:
            st.caption("Add a valid archive and a case ID to continue.")

        if st.button(btn_label,
                     type="primary",
                     disabled=not ready,
                     width="stretch",
                     key="batch_start"):
            log_action(
                action=f"Started batch analysis of {valid_count} images",
                case_id=meta.get("case_id", "—"),
                details=f"sensor={meta.get('sensor')}, ignored={summary['ignored']}",
            )
            st.session_state.current_batch = {
                "files": summary["files"],
                "ignored": summary["ignored"],
                "meta": meta,
                "results": [],
                "started_at": None,
            }
            st.session_state.current_page = "processing"
            st.rerun()

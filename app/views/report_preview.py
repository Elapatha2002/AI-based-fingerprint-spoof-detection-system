"""Screen 7 — Report Preview."""
from datetime import datetime
import streamlit as st
import base64

from components.cards import page_title, banner
from components.case_strip import render_case_strip
from components.audit import log_action, render_audit_drawer
from utils.report_generator import build_report
from app.services import email_delivery


def render():
    target = st.session_state.get("current_report_target")
    if not target:
        st.warning("No report target.")
        if st.button("Back"):
            st.session_state.current_page = "single_result"
            st.rerun()
        return

    filename = target["filename"]
    meta = target["meta"]
    result = target["result"]
    xai = target["xai"]
    report_key = (str(meta.get("case_id", "")), str(filename))
    if st.session_state.get("rp_email_report_key") != report_key:
        st.session_state["rp_email_report_key"] = report_key
        st.session_state["rp_email_open"] = False
        st.session_state["rp_email_nonce"] = st.session_state.get(
            "rp_email_nonce", 0
        ) + 1

    strip_meta = dict(meta)
    strip_meta.setdefault("timestamp",
                          datetime.now().isoformat(timespec="seconds"))
    render_case_strip(strip_meta,
                      status=st.session_state.get("case_status", "In Review"))

    page_title(
        "Report Preview",
        f"{filename} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )

    case_meta = {
        "case_id": meta.get("case_id", "—"),
        "examiner": meta.get("examiner", "—"),
        "sensor": meta.get("sensor", "—"),
        "notes": meta.get("notes", ""),
        "timestamp": meta.get("timestamp"),
    }

    xai_panels = [
        ("Grad-CAM++", xai["gradcam"]["image"]),
        ("SHAP", xai["shap"]["image"]),
        ("LIME", xai["lime"]["image"]),
    ]

    with st.spinner("Composing PDF..."):
        pdf_bytes = build_report(case_meta, result,
                                 image_bytes=target.get("image_bytes"),
                                 xai_panels=xai_panels)

    cols = st.columns([1, 2.5])

    with cols[0]:
        st.markdown(
            "<div class='fsd-section-h'>Report Pages</div>",
            unsafe_allow_html=True,
        )
        for i, label in enumerate(
                ["Page 1 — Header",
                 "Page 2 — Image + Verdict",
                 "Page 3 — XAI",
                 "Page 4 — Method + Sigs"], start=1):
            st.markdown(
                f"<div class='fsd-card' style='padding:10px;font-size:12px;'>"
                f"<b>Page {i}</b><br/>"
                f"<span style='color:var(--text-muted)'>{label[8:]}</span></div>",
                unsafe_allow_html=True,
            )

    with cols[1]:
        st.markdown(
            "<div class='fsd-section-h'>Preview</div>",
            unsafe_allow_html=True,
        )
        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(
            f"""<iframe src="data:application/pdf;base64,{b64}"
                width="100%" height="600"
                style="border:1px solid var(--border-subtle);
                border-radius:8px;background:white;"></iframe>""",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)

    banner(
        "Report includes: Case header ✓ &nbsp; Image ✓ &nbsp; Grad-CAM++ ✓ "
        "&nbsp; SHAP ✓ &nbsp; LIME ✓ &nbsp; Methodology ✓ &nbsp; Signatures ✓",
        kind="info",
    )

    a1, a2, a3, _ = st.columns([1, 1, 1, 3])
    with a1:
        clicked = st.download_button(
            "⬇  Download PDF",
            data=pdf_bytes,
            file_name=f"{meta.get('case_id', 'report')}_{filename}.pdf",
            mime="application/pdf",
            type="primary",
            width="stretch",
        )
        if clicked:
            log_action(
                action=f"Downloaded forensic report",
                case_id=meta.get("case_id", "—"),
                details=f"file={filename}, size={len(pdf_bytes)} bytes",
            )

            # Also archive the PDF in the active storage backend and record it in the DB. A
            # separate flag keeps this from running twice within a rerun.
            arch_key = f"report_archived_{meta.get('case_id')}_{filename}"
            if not st.session_state.get(arch_key):
                try:
                    from app.services import persistence
                    rid = persistence.save_report_to_cloud(
                        case_id=meta.get("case_id", "—"),
                        pdf_bytes=pdf_bytes,
                        examiner=meta.get("examiner", ""),
                    )
                    if rid:
                        st.session_state[arch_key] = True
                        from app.services import storage
                        archive_location = ("local storage" if isinstance(
                            storage.get_storage(), storage.LocalStorageService
                        ) else "cloud storage")
                        st.toast(f"Report archived to {archive_location} ({rid}).",
                                 icon="☁")
                        log_action(
                            action="Archived report to storage + SQLite",
                            case_id=meta.get("case_id", "—"),
                            details=f"report_id={rid}",
                        )
                except Exception:
                    pass
    with a2:
        if st.button("✉  Email PDF", width="stretch",
                     key="rp_email"):
            st.session_state["rp_email_open"] = not st.session_state.get(
                "rp_email_open", False
            )
    with a3:
        if st.button("◀  Back", width="stretch", key="rp_back"):
            st.session_state.pop("rp_email_open", None)
            st.session_state.current_page = "single_result"
            st.rerun()

    if st.session_state.get("rp_email_open"):
        if not email_delivery.email_is_configured():
            st.warning(
                "Email is not configured on this server. Ask the administrator "
                "to set the SMTP options described in app/README.md."
            )
        else:
            nonce = st.session_state.get("rp_email_nonce", 0)
            with st.form(f"rp_email_form_{nonce}", clear_on_submit=False):
                recipient = st.text_input(
                    "Recipient email address", key=f"rp_email_recipient_{nonce}",
                    placeholder="examiner@example.com",
                )
                confirmed = st.checkbox(
                    "I have checked this recipient is authorised to receive this report.",
                    key=f"rp_email_confirmed_{nonce}",
                )
                send_clicked = st.form_submit_button("Send PDF", type="primary")
            if send_clicked:
                if not confirmed:
                    st.error("Confirm the recipient before sending the report.")
                else:
                    try:
                        with st.spinner("Submitting email to the mail server..."):
                            receipt = email_delivery.send_report(
                                recipient=recipient,
                                case_id=meta.get("case_id", ""),
                                filename=filename,
                                pdf_bytes=pdf_bytes,
                            )
                    except (ValueError, email_delivery.EmailDeliveryError) as error:
                        st.error(str(error))
                    else:
                        log_action(
                            action="Submitted report email",
                            case_id=meta.get("case_id", "—"),
                            details=(
                                f"recipient={receipt.recipient}, "
                                f"message_id={receipt.message_id}, "
                                f"pdf_sha256={receipt.pdf_sha256}"
                            ),
                        )
                        st.success(
                            f"Mail server accepted the report for {receipt.recipient}."
                        )
                        st.session_state["rp_email_open"] = False
                        st.session_state["rp_email_nonce"] = nonce + 1

    st.markdown("<div class='fsd-divider'></div>", unsafe_allow_html=True)

    # Audit drawer at the bottom of the report page
    render_audit_drawer(case_id=meta.get("case_id"), expanded=False)

"""Email report delivery checks without contacting an external mail server."""

import hashlib
import os
import smtplib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services import email_delivery

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


SMTP_ENV = {
    "SMTP_HOST": "mail.example.com",
    "SMTP_PORT": "465",
    "SMTP_SECURITY": "ssl",
    "SMTP_USERNAME": "reports@example.com",
    "SMTP_PASSWORD": "test-only-secret",
    "SMTP_FROM_EMAIL": "reports@example.com",
}
PDF = b"%PDF-1.7\nfixture report"


class ReportEmailTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, SMTP_ENV))

    def test_ssl_submission_attaches_pdf_and_returns_receipt(self):
        server = MagicMock()
        server.__enter__.return_value = server
        server.send_message.return_value = {}
        with patch.object(email_delivery.smtplib, "SMTP_SSL", return_value=server) as smtp:
            receipt = email_delivery.send_report(
                recipient="reviewer@example.com", case_id="CASE-123",
                filename="finger.bmp", pdf_bytes=PDF,
            )
        smtp.assert_called_once()
        server.login.assert_called_once_with("reports@example.com", "test-only-secret")
        sent = server.send_message.call_args.args[0]
        self.assertEqual(sent["To"], "reviewer@example.com")
        self.assertEqual(sent["From"], "reports@example.com")
        self.assertEqual(sent["Subject"], "FSD-XAI report: CASE-123")
        attachment = next(sent.iter_attachments())
        self.assertEqual(attachment.get_content(), PDF)
        self.assertEqual(attachment.get_filename(), "CASE-123_finger.bmp.pdf")
        self.assertEqual(receipt.pdf_sha256, hashlib.sha256(PDF).hexdigest())
        self.assertEqual(receipt.message_id, sent["Message-ID"])

    def test_starttls_is_negotiated_before_login(self):
        server = MagicMock()
        server.__enter__.return_value = server
        server.send_message.return_value = {}
        with patch.dict(os.environ, {"SMTP_SECURITY": "starttls", "SMTP_PORT": "587"}):
            with patch.object(email_delivery.smtplib, "SMTP", return_value=server) as smtp:
                email_delivery.send_report(
                    recipient="reviewer@example.com", case_id="CASE-123",
                    filename="finger.bmp", pdf_bytes=PDF,
                )
        smtp.assert_called_once()
        server.starttls.assert_called_once()
        calls = [call[0] for call in server.method_calls]
        self.assertLess(calls.index("starttls"), calls.index("login"))

    def test_invalid_recipient_does_not_contact_server(self):
        with patch.object(email_delivery.smtplib, "SMTP_SSL") as smtp:
            with self.assertRaisesRegex(ValueError, "one valid email address"):
                email_delivery.send_report(
                    recipient="reviewer@example.com, other@example.com",
                    case_id="CASE-123", filename="finger.bmp", pdf_bytes=PDF,
                )
        smtp.assert_not_called()

    def test_missing_configuration_is_clear(self):
        with patch.dict(os.environ, {"SMTP_PASSWORD": ""}):
            with self.assertRaisesRegex(email_delivery.EmailConfigurationError,
                                        "SMTP_PASSWORD"):
                email_delivery.smtp_settings()

    def test_authentication_failure_is_reported_without_secret(self):
        server = MagicMock()
        server.__enter__.return_value = server
        server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"test-only-secret rejected"
        )
        with patch.object(email_delivery.smtplib, "SMTP_SSL", return_value=server):
            with self.assertRaises(email_delivery.EmailDeliveryError) as caught:
                email_delivery.send_report(
                    recipient="reviewer@example.com", case_id="CASE-123",
                    filename="finger.bmp", pdf_bytes=PDF,
                )
        self.assertNotIn("test-only-secret", str(caught.exception))

    def test_report_page_confirms_before_sending_and_audits_acceptance(self):
        from streamlit.testing.v1 import AppTest
        from views import report_preview

        script = """
from views.report_preview import render
render()
"""
        target = {
            "filename": "finger.bmp",
            "meta": {"case_id": "CASE-123", "examiner": "Fixture Examiner"},
            "result": {"label": "live"},
            "xai": {name: {"image": b"fixture"}
                    for name in ("gradcam", "shap", "lime")},
        }
        receipt = email_delivery.DeliveryReceipt(
            recipient="reviewer@example.com", message_id="<fixture@example.com>",
            pdf_sha256=hashlib.sha256(PDF).hexdigest(),
        )
        with patch.object(report_preview, "build_report", return_value=PDF), \
             patch.object(report_preview, "render_case_strip"), \
             patch.object(report_preview, "page_title"), \
             patch.object(report_preview, "banner"), \
             patch.object(report_preview, "render_audit_drawer"), \
             patch.object(report_preview, "log_action") as audit, \
             patch.object(email_delivery, "send_report", return_value=receipt) as send:
            app = AppTest.from_string(script)
            app.session_state["current_report_target"] = target
            app.run()
            self.assertFalse(app.exception)
            app.button(key="rp_email").click().run()
            self.assertFalse(app.exception)
            nonce = app.session_state["rp_email_nonce"]
            app.text_input(key=f"rp_email_recipient_{nonce}").input(
                "reviewer@example.com"
            ).run()
            next(button for button in app.button if button.label == "Send PDF").click().run()
            self.assertFalse(app.exception)
            send.assert_not_called()
            self.assertIn("Confirm the recipient", app.error[0].value)

            app.checkbox(key=f"rp_email_confirmed_{nonce}").check().run()
            next(button for button in app.button if button.label == "Send PDF").click().run()
            self.assertFalse(app.exception)
            send.assert_called_once_with(
                recipient="reviewer@example.com", case_id="CASE-123",
                filename="finger.bmp", pdf_bytes=PDF,
            )
            audit.assert_called_once()
            self.assertEqual(audit.call_args.kwargs["action"], "Submitted report email")
            self.assertIn("accepted the report", app.success[0].value)


if __name__ == "__main__":
    unittest.main()

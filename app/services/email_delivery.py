"""Send generated forensic PDF reports through a configured SMTP account."""

from __future__ import annotations

import hashlib
import os
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid


MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
_ADDRESS = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\Z"
)


class EmailConfigurationError(ValueError):
    """SMTP settings are missing or invalid."""


class EmailDeliveryError(RuntimeError):
    """The configured mail server did not accept the report."""


@dataclass(frozen=True)
class DeliveryReceipt:
    recipient: str
    message_id: str
    pdf_sha256: str


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    sender: str
    security: str


def validate_address(value: str) -> str:
    """Accept one plain mailbox address, not a list or display-name header."""
    address = value.strip()
    if (
        len(address) > 254
        or not address.isascii()
        or not _ADDRESS.fullmatch(address)
        or ".." in address
        or address.startswith(".")
        or ".@" in address
        or "-." in address
        or ".-" in address
    ):
        raise ValueError("Enter one valid email address, without a display name.")
    return address


def smtp_settings() -> SmtpSettings:
    """Read server-side settings only; no credentials are entered in the UI."""
    fields = {
        key: os.environ.get(key, "").strip()
        for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_FROM_EMAIL")
    }
    fields["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD", "")
    missing = [key for key, value in fields.items() if not value.strip()]
    if missing:
        raise EmailConfigurationError(
            "Email is not configured. Ask the administrator to set: "
            + ", ".join(missing) + "."
        )
    security = os.environ.get("SMTP_SECURITY", "ssl").strip().lower()
    if security not in {"ssl", "starttls"}:
        raise EmailConfigurationError("SMTP_SECURITY must be ssl or starttls.")
    raw_port = os.environ.get("SMTP_PORT", "465" if security == "ssl" else "587")
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as error:
        raise EmailConfigurationError("SMTP_PORT must be a valid port number.") from error
    if not 1 <= port <= 65535:
        raise EmailConfigurationError("SMTP_PORT must be between 1 and 65535.")
    try:
        sender = validate_address(fields["SMTP_FROM_EMAIL"])
    except ValueError as error:
        raise EmailConfigurationError("SMTP_FROM_EMAIL must be a valid email address.") from error
    return SmtpSettings(
        host=fields["SMTP_HOST"], port=port,
        username=fields["SMTP_USERNAME"], password=fields["SMTP_PASSWORD"],
        sender=sender, security=security,
    )


def email_is_configured() -> bool:
    try:
        smtp_settings()
    except EmailConfigurationError:
        return False
    return True


def send_report(*, recipient: str, case_id: str, filename: str,
                pdf_bytes: bytes) -> DeliveryReceipt:
    """Submit one PDF to SMTP; return a receipt after server acceptance."""
    address = validate_address(recipient)
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("The generated report is not a valid PDF attachment.")
    if len(pdf_bytes) > MAX_ATTACHMENT_BYTES:
        raise ValueError("The report is too large to email; download the PDF instead.")
    settings = smtp_settings()

    safe_case = re.sub(r"[^A-Za-z0-9._-]+", "-", str(case_id)).strip(".-_")[:64]
    safe_case = safe_case or "case"
    safe_name = re.sub(
        r"[^A-Za-z0-9._-]+", "_", str(filename).replace("\\", "/").split("/")[-1]
    ).strip("._")[:80]
    attachment_name = f"{safe_case}_{safe_name or 'report'}.pdf"

    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = address
    message["Subject"] = f"FSD-XAI report: {safe_case}"
    message["Message-ID"] = make_msgid(domain=settings.sender.rsplit("@", 1)[1])
    message.set_content(
        f"Attached is the FSD-XAI report for case {safe_case}.\n\n"
        "This report contains forensic case information. Share and retain it "
        "according to your organisation's procedures.\n"
    )
    message.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=attachment_name
    )

    context = ssl.create_default_context()
    try:
        if settings.security == "ssl":
            with smtplib.SMTP_SSL(
                settings.host, settings.port, timeout=20, context=context
            ) as server:
                server.login(settings.username, settings.password)
                refused = server.send_message(message)
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(settings.username, settings.password)
                refused = server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError(
            "The mail server did not accept the report. Check SMTP settings "
            "and try again."
        ) from error
    if refused:
        raise EmailDeliveryError("The mail server refused the recipient address.")

    return DeliveryReceipt(
        recipient=address,
        message_id=str(message["Message-ID"]),
        pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )

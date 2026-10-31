"""SMTP transport with verified TLS, standard headers and a dry-run mode.

Secrets are read from the environment and never logged. When EMAIL_DRY_RUN is
truthy, messages are written as .eml files to EMAIL_OUTBOX_DIR (default
data/outbox) instead of being sent; tests force this mode so no real e-mail can
leave a test run.
"""
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

from src.config import ROOT, get_secret

log = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on"}


def is_dry_run() -> bool:
    return str(os.getenv("EMAIL_DRY_RUN", "")).strip().lower() in _TRUE


def build_message(subject: str, text_body: str, html_body: str | None,
                  sender: str, recipient: str) -> EmailMessage:
    """Build a multipart/alternative message: plain text first, HTML second."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = format_datetime(datetime.now(timezone.utc))
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else "etf-wealth-builder.local"
    msg["Message-ID"] = make_msgid(domain=domain)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    return msg


def _write_outbox(msg: EmailMessage) -> Path:
    outbox = Path(os.getenv("EMAIL_OUTBOX_DIR") or (ROOT / "data" / "outbox"))
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = outbox / f"email_{stamp}.eml"
    path.write_bytes(bytes(msg))
    return path


def send_email(subject: str, body: str, html_body: str | None = None) -> bool:
    """Send a multipart e-mail. Returns True only if a message was really sent.

    Never raises: SMTP and network errors are logged (type only) and reported
    as False so that one failed notification cannot abort the daily cycle.
    """
    sender = get_secret("EMAIL_FROM") or "etf-wealth-builder@localhost"
    recipient = get_secret("EMAIL_TO") or "dry-run@localhost"
    msg = build_message(subject, body, html_body, sender, recipient)

    if is_dry_run():
        path = _write_outbox(msg)
        log.info("EMAIL_DRY_RUN active: message written to %s, not sent", path)
        return False

    host = get_secret("SMTP_HOST")
    username = get_secret("SMTP_USERNAME")
    password = get_secret("SMTP_PASSWORD")
    if not all([host, username, password, get_secret("EMAIL_FROM"), get_secret("EMAIL_TO")]):
        log.warning("E-mail not sent: SMTP configuration is incomplete")
        return False

    try:
        port = int(get_secret("SMTP_PORT") or "587")
    except ValueError:
        log.warning("E-mail not sent: SMTP_PORT is not an integer")
        return False

    context = ssl.create_default_context()  # verifies certificate and hostname
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
                server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=context)
                server.login(username, password)
                server.send_message(msg)
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        log.error("E-mail delivery failed: %s", type(exc).__name__)
        return False
    log.info("E-mail sent: %s", subject)
    return True

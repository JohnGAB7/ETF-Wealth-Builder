import smtplib
import ssl
from email import message_from_bytes

import pytest

from src.notifications import transport


def test_dry_run_writes_eml_and_never_sends(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_OUTBOX_DIR", str(tmp_path))
    assert transport.send_email("Sujet", "texte", "<p>html</p>") is False
    files = list(tmp_path.glob("*.eml"))
    assert len(files) == 1
    msg = message_from_bytes(files[0].read_bytes())
    assert msg["Subject"] == "Sujet"
    assert msg["Date"] and msg["Message-ID"]
    assert msg.is_multipart()
    types = [part.get_content_type() for part in msg.walk()]
    assert "text/plain" in types and "text/html" in types


def test_build_message_puts_plain_text_before_html():
    msg = transport.build_message("S", "plain", "<b>h</b>", "a@example.org", "b@example.org")
    parts = [p.get_content_type() for p in msg.iter_parts()]
    assert parts == ["text/plain", "text/html"]
    assert msg["Message-ID"].endswith("@example.org>")


def _configure(monkeypatch, port="587"):
    monkeypatch.delenv("EMAIL_DRY_RUN", raising=False)
    for name, value in {"SMTP_HOST": "smtp.example.org", "SMTP_PORT": port,
                        "SMTP_USERNAME": "user", "SMTP_PASSWORD": "pw",
                        "EMAIL_FROM": "a@example.org", "EMAIL_TO": "b@example.org"}.items():
        monkeypatch.setenv(name, value)


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.context = context
        self.starttls_context = None
        self.sent = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.starttls_context = context

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.sent.append(msg)


def test_starttls_verifies_certificates(monkeypatch):
    _configure(monkeypatch)
    _FakeSMTP.instances = []
    monkeypatch.setattr(transport.smtplib, "SMTP", _FakeSMTP)
    assert transport.send_email("S", "t") is True
    ctx = _FakeSMTP.instances[0].starttls_context
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_port_465_uses_implicit_tls(monkeypatch):
    _configure(monkeypatch, port="465")
    _FakeSMTP.instances = []
    monkeypatch.setattr(transport.smtplib, "SMTP_SSL", _FakeSMTP)
    assert transport.send_email("S", "t") is True
    assert _FakeSMTP.instances[0].context.verify_mode == ssl.CERT_REQUIRED


def test_smtp_failure_is_logged_without_raising_or_leaking(monkeypatch, caplog):
    _configure(monkeypatch)

    class Broken(_FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials pw")

    monkeypatch.setattr(transport.smtplib, "SMTP", Broken)
    assert transport.send_email("S", "t") is False
    assert "SMTPAuthenticationError" in caplog.text
    assert "pw" not in caplog.text.replace("SMTP", "")


def test_incomplete_configuration_returns_false(monkeypatch, caplog):
    monkeypatch.delenv("EMAIL_DRY_RUN", raising=False)
    assert transport.send_email("S", "t") is False
    assert "incomplete" in caplog.text


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_dry_run_flag_values(monkeypatch, value):
    monkeypatch.setenv("EMAIL_DRY_RUN", value)
    assert transport.is_dry_run()

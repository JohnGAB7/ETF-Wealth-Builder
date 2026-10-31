"""Global safety net: no test may send a real e-mail or use real SMTP secrets."""
import pytest

_SECRET_VARS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
                "EMAIL_FROM", "EMAIL_TO", "VALUEINVESTING_API_KEY", "FINNHUB_API_KEY",
                "FRED_API_KEY"]


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch, tmp_path):
    for name in _SECRET_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EMAIL_DRY_RUN", "1")
    monkeypatch.setenv("EMAIL_OUTBOX_DIR", str(tmp_path / "outbox"))

    def _forbidden(*args, **kwargs):
        raise AssertionError("A test tried to open a real SMTP connection")

    monkeypatch.setattr("smtplib.SMTP", _forbidden)
    monkeypatch.setattr("smtplib.SMTP_SSL", _forbidden)

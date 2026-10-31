"""Public e-mail entry points used by src.main.

Content is built once by view_model, rendered by render (HTML + plain text) and
delivered by transport. `send_email` is re-exported here so callers and tests can
patch a single name.
"""
from src.notifications.render import render_html, render_text
from src.notifications.transport import send_email
from src.notifications.view_model import (  # noqa: F401  (re-exported)
    MACRO_DIGEST_FIELDS, SIGNAL_LABELS, build_alert_view, build_digest_view,
    format_macro_digest,
)


def compose_digest(results, run_date, macro_snapshot=None, strategy=None):
    """Return (subject, text, html) without sending anything."""
    view = build_digest_view(results, run_date, macro_snapshot, strategy)
    return view["subject"], render_text(view), render_html(view)


def compose_signal_alert(result, horizon_days=None, strategy=None, run_date=None):
    view = build_alert_view(result, horizon_days, strategy, run_date)
    return view["subject"], render_text(view), render_html(view)


def send_digest(results: list[dict], run_date: str, macro_snapshot: dict | None = None,
                strategy: dict | None = None) -> bool:
    subject, text, html = compose_digest(results, run_date, macro_snapshot, strategy)
    return send_email(subject, text, html_body=html)


def send_signal_alert(result: dict, horizon_days: int, strategy: dict | None = None,
                      run_date: str | None = None) -> bool:
    """Send a research alert when an ETF meets the review thresholds."""
    subject, text, html = compose_signal_alert(result, horizon_days, strategy, run_date)
    return send_email(subject, text, html_body=html)

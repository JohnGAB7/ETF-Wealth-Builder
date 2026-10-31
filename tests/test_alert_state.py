import json

from src.notifications.email_alert import compose_digest
from src.state.alert_state import (
    REVIEW, load_state, previous_signals, record_alert, record_signal, save_state,
    should_alert,
)


def _run(state, signal, day, sent_ok=True, **kw):
    due, reason = should_alert(state, "vwce", signal, day, **kw)
    if due and sent_ok:
        record_alert(state, "vwce", day)
    record_signal(state, "vwce", signal, day)
    return due, reason


def test_one_alert_per_review_episode():
    state = load_state("/nonexistent/state.json")
    assert _run(state, "WATCH", "2026-10-27") == (False, "not_review")
    assert _run(state, REVIEW, "2026-10-28") == (True, "new_episode")
    assert _run(state, REVIEW, "2026-10-29") == (False, "already_alerted_this_episode")
    assert _run(state, REVIEW, "2026-10-30")[0] is False
    _run(state, "WATCH", "2026-11-02")
    assert _run(state, REVIEW, "2026-11-03") == (True, "new_episode")


def test_failed_delivery_is_retried_next_run():
    state = {"version": 1, "etfs": {}}
    assert _run(state, REVIEW, "2026-10-28", sent_ok=False)[0] is True
    assert _run(state, REVIEW, "2026-10-29") == (True, "retry_or_repeat")
    assert _run(state, REVIEW, "2026-10-30")[0] is False


def test_daily_cap_applies_even_without_upgrade_only():
    state = {"version": 1, "etfs": {}}
    assert _run(state, REVIEW, "2026-10-28", upgrade_only=False)[0] is True
    # Same day re-run (manual workflow dispatch): capped.
    assert should_alert(state, "vwce", REVIEW, "2026-10-28", upgrade_only=False) == (False, "daily_cap")
    # Next day, repeat allowed when upgrade_only is off.
    assert should_alert(state, "vwce", REVIEW, "2026-10-29", upgrade_only=False)[0] is True


def test_state_round_trip_and_corruption(tmp_path):
    path = tmp_path / "state" / "alert_state.json"
    state = {"version": 1, "etfs": {}}
    record_signal(state, "vwce", "WATCH", "2026-10-28")
    save_state(state, path)
    assert load_state(path)["etfs"]["vwce"]["last_signal"] == "WATCH"
    path.write_text("{not json")
    assert load_state(path) == {"version": 1, "etfs": {}}
    path.write_text(json.dumps(["wrong"]))
    assert load_state(path)["etfs"] == {}


def test_previous_signals_and_since_date():
    state = {"version": 1, "etfs": {}}
    record_signal(state, "vwce", "WATCH", "2026-10-27")
    record_signal(state, "vwce", "WATCH", "2026-10-28")
    prev = previous_signals(state)["vwce"]
    assert prev == {"signal": "WATCH", "since": "2026-10-27", "date": "2026-10-28"}


def test_old_alert_counters_are_pruned():
    state = {"version": 1, "etfs": {}}
    for day in range(1, 41):
        record_alert(state, "vwce", f"2026-01-{day:02d}" if day <= 31 else f"2026-02-{day - 31:02d}")
    assert len(state["etfs"]["vwce"]["alerts_by_date"]) == 31


def test_digest_shows_status_changes():
    item = {"id": "cspx", "name": "S&P", "symbol": "CSPX.L", "signal": REVIEW, "score": 78,
            "previous_signal": "WATCH", "previous_signal_date": "2026-10-29"}
    same = {"id": "vwce", "name": "All-World", "symbol": "VWCE.DE", "signal": "WATCH",
            "score": 60, "previous_signal": "WATCH", "previous_signal_since": "2026-10-20"}
    _, text, html = compose_digest([item, same], "2026-10-30")
    assert "Depuis le dernier rapport : CSPX.L à surveiller → opportunité à examiner." in text
    assert "Changement : À surveiller → Opportunité à examiner (précédent rapport du 29/10/2026)" in text
    assert "Inchangé depuis le 20/10/2026" in text
    assert "▲" in html
    _, text, _ = compose_digest([same], "2026-10-30")
    assert "Aucun changement de statut depuis le dernier rapport." in text

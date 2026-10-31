"""Persistent signal and alert state, used to avoid repeating the same alert.

Stored as JSON in data/state/alert_state.json (git-ignored; persisted between
GitHub Actions runs by the workflow cache). The format is deliberately small:

    {"version": 1,
     "etfs": {"vwce": {"last_signal": "WATCH", "last_run_date": "2026-10-30",
                       "signal_since": "2026-10-28",
                       "alert_sent_for_episode": false,
                       "alerts_by_date": {"2026-10-30": 1}}}}

An *episode* is a run of consecutive reports with BUY_OPPORTUNITY_REVIEW. With
`email_on_signal_upgrade_only`, one alert is sent per episode; the flag is reset
when the signal leaves that status. A failed delivery does not close the episode,
so the alert is retried at the next run. A missing or unreadable state file is
treated as a first run (an alert may then be repeated once, never lost).
"""
import json
import logging
from pathlib import Path

from src.config import ROOT

log = logging.getLogger(__name__)

REVIEW = "BUY_OPPORTUNITY_REVIEW"
STATE_VERSION = 1
DEFAULT_PATH = ROOT / "data" / "state" / "alert_state.json"
KEEP_ALERT_DAYS = 31  # prune per-day counters older than this many entries


def load_state(path: Path = DEFAULT_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {"version": STATE_VERSION, "etfs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("etfs"), dict):
            raise ValueError("unexpected structure")
        return data
    except (OSError, ValueError) as exc:
        log.warning("Alert state unreadable (%s); starting from an empty state",
                    type(exc).__name__)
        return {"version": STATE_VERSION, "etfs": {}}


def save_state(state: dict, path: Path = DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _entry(state: dict, etf_id: str) -> dict:
    return state.setdefault("etfs", {}).setdefault(str(etf_id), {})


def previous_signals(state: dict) -> dict:
    """{etf_id: {"signal": ..., "since": ..., "date": ...}} from the last run."""
    out = {}
    for etf_id, entry in (state.get("etfs") or {}).items():
        if entry.get("last_signal"):
            out[etf_id] = {"signal": entry["last_signal"], "since": entry.get("signal_since"),
                           "date": entry.get("last_run_date")}
    return out


def should_alert(state: dict, etf_id: str, signal: str, run_date: str,
                 upgrade_only: bool = True, max_per_day: int = 1) -> tuple[bool, str]:
    """Decide whether an immediate alert is due. Returns (decision, reason code)."""
    if signal != REVIEW:
        return False, "not_review"
    entry = (state.get("etfs") or {}).get(str(etf_id), {})
    sent_today = int((entry.get("alerts_by_date") or {}).get(run_date, 0))
    if max_per_day is not None and sent_today >= int(max_per_day):
        return False, "daily_cap"
    if upgrade_only and entry.get("last_signal") == REVIEW and entry.get("alert_sent_for_episode"):
        return False, "already_alerted_this_episode"
    return True, "new_episode" if entry.get("last_signal") != REVIEW else "retry_or_repeat"


def record_alert(state: dict, etf_id: str, run_date: str) -> None:
    entry = _entry(state, etf_id)
    counts = entry.setdefault("alerts_by_date", {})
    counts[run_date] = int(counts.get(run_date, 0)) + 1
    for day in sorted(counts)[:-KEEP_ALERT_DAYS]:
        counts.pop(day, None)
    entry["alert_sent_for_episode"] = True


def record_signal(state: dict, etf_id: str, signal: str, run_date: str) -> None:
    entry = _entry(state, etf_id)
    if entry.get("last_signal") != signal:
        entry["signal_since"] = run_date
        if signal != REVIEW:
            entry["alert_sent_for_episode"] = False
    entry["last_signal"] = signal
    entry["last_run_date"] = run_date
    entry.setdefault("alert_sent_for_episode", False)
    state["version"] = STATE_VERSION

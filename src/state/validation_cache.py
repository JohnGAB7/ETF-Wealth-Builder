"""Weekly cache of the out-of-sample validation (lot 5.1, observation mode).

The purged walk-forward refits the model about ten times per ETF; it is far too
slow to run daily. Results are stored in data/state/validation_cache.json (same
GitHub Actions cache as the alert state) with their computation date and a small
fingerprint of what was validated. A result is reused while it is younger than
`refresh_days` and its fingerprint matches; otherwise it is recomputed.
"""
import json
import logging
from datetime import date
from pathlib import Path

from src.config import ROOT

log = logging.getLogger(__name__)

CACHE_VERSION = 1
# Bump when the validation protocol changes, so stale results are recomputed.
PROTOCOL_VERSION = "5.1-purged-wf-1"
DEFAULT_PATH = ROOT / "data" / "state" / "validation_cache.json"


def load_cache(path: Path | None = None) -> dict:
    path = Path(path or DEFAULT_PATH)
    if not path.exists():
        return {"version": CACHE_VERSION, "etfs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("etfs"), dict):
            raise ValueError("unexpected structure")
        return data
    except (OSError, ValueError) as exc:
        log.warning("Validation cache unreadable (%s): recomputing", type(exc).__name__)
        return {"version": CACHE_VERSION, "etfs": {}}


def save_cache(cache: dict, path: Path | None = None) -> None:
    path = Path(path or DEFAULT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2, allow_nan=False),
                   encoding="utf-8")
    tmp.replace(path)


def fingerprint(symbol: str, first_date: str, horizon: int, test_block: int) -> dict:
    return {"symbol": symbol, "first_date": first_date, "horizon": horizon,
            "test_block": test_block, "protocol": PROTOCOL_VERSION}


def get_fresh(cache: dict, etf_id: str, fp: dict, run_date: str, refresh_days: int):
    entry = cache.get("etfs", {}).get(etf_id)
    if not entry or entry.get("fingerprint") != fp:
        return None
    try:
        age = (date.fromisoformat(run_date) - date.fromisoformat(entry["computed_at"])).days
    except (KeyError, TypeError, ValueError):
        return None
    return entry.get("summary") if 0 <= age < refresh_days else None


def put(cache: dict, etf_id: str, fp: dict, run_date: str, summary: dict) -> None:
    cache.setdefault("etfs", {})[etf_id] = {
        "computed_at": run_date, "fingerprint": fp, "summary": summary}

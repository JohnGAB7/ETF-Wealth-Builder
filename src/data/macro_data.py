import logging
import requests
import pandas as pd
from src.config import get_secret

log = logging.getLogger(__name__)
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# A small starter set. Expand and document each series' economic meaning and release lag.
DEFAULT_SERIES = {
    "FEDFUNDS": "policy_rate_us",
    "CPIAUCSL": "us_cpi",
    "UNRATE": "us_unemployment",
    "DGS10": "us_10y_yield",
    "T10Y2Y": "us_10y_2y_spread",
    "BAMLH0A0HYM2": "us_high_yield_spread",
}

def get_fred_series(series_id: str, start: str = "2000-01-01") -> pd.Series:
    key = get_secret("FRED_API_KEY")
    if not key:
        return pd.Series(dtype=float, name=series_id)
    try:
        r = requests.get(FRED_URL, params={
            "series_id": series_id, "api_key": key, "file_type": "json",
            "observation_start": start,
        }, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        frame = pd.DataFrame(obs)
        if frame.empty:
            return pd.Series(dtype=float, name=series_id)
        frame["date"] = pd.to_datetime(frame["date"])
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        return frame.set_index("date")["value"].dropna().rename(series_id)
    except Exception as exc:
        log.warning("FRED %s unavailable: %s", series_id, type(exc).__name__)
        return pd.Series(dtype=float, name=series_id)

def get_macro_snapshot() -> dict:
    snapshot = {}
    for series_id, label in DEFAULT_SERIES.items():
        series = get_fred_series(series_id)
        snapshot[label] = float(series.iloc[-1]) if not series.empty else None
        snapshot[label + "_date"] = str(series.index[-1].date()) if not series.empty else None
    return snapshot

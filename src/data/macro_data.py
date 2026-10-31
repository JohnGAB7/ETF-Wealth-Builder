import logging
import requests
import pandas as pd
from src.config import get_secret
from src.data.ecb_data import get_ecb_snapshot
from src.data.eurostat_data import get_eurostat_snapshot

log = logging.getLogger(__name__)
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# A compact US macro set; FRED API access is free but requires a registered API key.
DEFAULT_SERIES = {
    "FEDFUNDS": "us_policy_rate",
    "CPIAUCSL": "us_cpi_index",
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
        response = requests.get(
            FRED_URL,
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "observation_start": start,
            },
            headers={"User-Agent": "ETF-Wealth-Builder/0.2"},
            timeout=30,
        )
        response.raise_for_status()
        observations = response.json().get("observations", [])
        frame = pd.DataFrame(observations)
        if frame.empty:
            return pd.Series(dtype=float, name=series_id)
        frame["date"] = pd.to_datetime(frame["date"])
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        return frame.set_index("date")["value"].dropna().rename(series_id)
    except Exception as exc:
        log.warning("FRED %s unavailable: %s", series_id, type(exc).__name__)
        return pd.Series(dtype=float, name=series_id)


def get_macro_snapshot() -> dict:
    """Combine current US, euro-area and Belgian macro indicators.

    ECB and Eurostat are public and keyless. FRED is optional and requires FRED_API_KEY.
    These latest-value snapshots are contextual only; they are not backfilled into
    historical ML rows. Historical evaluation requires archived release/vintage data.
    """
    snapshot = {}

    for series_id, label in DEFAULT_SERIES.items():
        series = get_fred_series(series_id)
        snapshot[label] = float(series.iloc[-1]) if not series.empty else None
        snapshot[label + "_date"] = (
            str(series.index[-1].date()) if not series.empty else None
        )

    try:
        snapshot.update(get_ecb_snapshot())
    except Exception as exc:
        log.warning("ECB macro snapshot unavailable: %s", type(exc).__name__)

    try:
        snapshot.update(get_eurostat_snapshot())
    except Exception as exc:
        log.warning("Eurostat macro snapshot unavailable: %s", type(exc).__name__)

    return snapshot

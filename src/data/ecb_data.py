"""Free ECB Data Portal SDMX 2.1 data adapter.

No API key or paid subscription is required. The public ECB SDMX endpoint is used
for official euro-area policy rates and reference exchange rates.
"""
import logging
from io import StringIO

import pandas as pd
import requests

log = logging.getLogger(__name__)
ECB_BASE_URL = "https://data-api.ecb.europa.eu/service"
USER_AGENT = "ETF-Wealth-Builder/0.2 (+https://github.com/JohnGAB7/ETF-Wealth-Builder)"

DEFAULT_ECB_SERIES = {
    # ECB deposit facility rate: daily, percent per annum, euro area.
    "ecb_deposit_facility_rate": ("FM", "D.U2.EUR.4F.KR.DFR.LEV"),
    # USD per EUR: daily reference exchange rate (one EUR expressed in USD).
    "ecb_usd_per_eur": ("EXR", "D.USD.EUR.SP00.A"),
}


def parse_ecb_csv_series(content: str, name: str) -> pd.Series:
    """Parse ECB SDMX csvdata output into a numeric time series."""
    if not content or not content.strip():
        return pd.Series(dtype=float, name=name)
    try:
        frame = pd.read_csv(StringIO(content))
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.Series(dtype=float, name=name)

    columns = {str(column).upper(): column for column in frame.columns}
    time_column = columns.get("TIME_PERIOD")
    value_column = columns.get("OBS_VALUE")
    if time_column is None or value_column is None:
        return pd.Series(dtype=float, name=name)

    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    frame = frame.dropna(subset=[value_column, time_column])
    if frame.empty:
        return pd.Series(dtype=float, name=name)
    return pd.Series(
        frame[value_column].to_numpy(dtype=float),
        index=frame[time_column].astype(str),
        name=name,
        dtype=float,
    ).sort_index()


def get_ecb_series(
    flow: str,
    series_key: str,
    name: str,
    last_n: int = 6,
) -> pd.Series:
    """Retrieve the latest observations for one ECB SDMX series."""
    url = f"{ECB_BASE_URL}/data/{flow}/{series_key}"
    try:
        response = requests.get(
            url,
            params={
                "lastNObservations": max(1, int(last_n)),
                "format": "csvdata",
                "detail": "dataonly",
            },
            headers={"User-Agent": USER_AGENT, "Accept": "text/csv"},
            timeout=30,
        )
        response.raise_for_status()
        return parse_ecb_csv_series(response.text, name)
    except Exception as exc:
        # Do not log full URLs or untrusted response bodies.
        log.warning("ECB series %s unavailable: %s", name, type(exc).__name__)
        return pd.Series(dtype=float, name=name)


def get_ecb_snapshot() -> dict:
    """Return the latest ECB policy-rate and EUR/USD observations with dates."""
    snapshot = {}
    for label, (flow, key) in DEFAULT_ECB_SERIES.items():
        series = get_ecb_series(flow, key, label, last_n=6)
        snapshot[label] = float(series.iloc[-1]) if not series.empty else None
        snapshot[label + "_date"] = str(series.index[-1]) if not series.empty else None
    return snapshot

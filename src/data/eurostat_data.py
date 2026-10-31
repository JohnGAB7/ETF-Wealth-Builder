"""Free Eurostat Statistics API adapter using JSON-stat 2.0 responses.

The API is public and does not require an API key. Eurostat exposes current dataset
versions; historical vintages must be archived separately for point-in-time backtests.
"""
import logging

import pandas as pd
import requests

log = logging.getLogger(__name__)
EUROSTAT_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
)
USER_AGENT = "ETF-Wealth-Builder/0.2 (+https://github.com/JohnGAB7/ETF-Wealth-Builder)"


def parse_jsonstat_series(payload: dict, name: str = "value") -> pd.Series:
    """Extract a single filtered time series from a Eurostat JSON-stat 2.0 payload.

    Query filters should fix every non-time dimension (e.g. geo, unit, freq).
    The parser handles JSON-stat sparse dictionaries and dense arrays.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("dimension"), dict):
        return pd.Series(dtype=float, name=name)

    dimension_ids = payload.get("id", [])
    sizes = payload.get("size", [])
    dimensions = payload.get("dimension", {})
    if not dimension_ids or len(dimension_ids) != len(sizes):
        return pd.Series(dtype=float, name=name)

    time_position = next(
        (i for i, dimension_id in enumerate(dimension_ids)
         if str(dimension_id).lower() == "time"),
        None,
    )
    if time_position is None:
        return pd.Series(dtype=float, name=name)

    time_dimension_id = dimension_ids[time_position]
    time_dimension = dimensions.get(time_dimension_id, {})
    time_index = (
        time_dimension.get("category", {}).get("index", {})
        if isinstance(time_dimension, dict) else {}
    )
    if not isinstance(time_index, dict):
        return pd.Series(dtype=float, name=name)
    time_codes = {int(position): str(code) for code, position in time_index.items()}

    raw_values = payload.get("value", {})
    if isinstance(raw_values, dict):
        entries = raw_values.items()
    elif isinstance(raw_values, list):
        entries = enumerate(raw_values)
    else:
        return pd.Series(dtype=float, name=name)

    observations = {}
    normalized_sizes = [int(size) for size in sizes]
    for flat_index, raw_value in entries:
        if raw_value is None:
            continue
        try:
            numeric_value = float(raw_value)
            remaining = int(flat_index)
        except (TypeError, ValueError):
            continue

        coordinates = [0] * len(normalized_sizes)
        for position in range(len(normalized_sizes) - 1, -1, -1):
            size = normalized_sizes[position]
            if size <= 0:
                coordinates[position] = 0
                continue
            coordinates[position] = remaining % size
            remaining //= size

        period = time_codes.get(coordinates[time_position])
        if period is not None:
            observations[period] = numeric_value

    if not observations:
        return pd.Series(dtype=float, name=name)
    return pd.Series(observations, name=name, dtype=float).sort_index()


def get_eurostat_series(
    dataset_code: str,
    filters: dict,
    name: str,
    last_n_periods: int = 6,
) -> pd.Series:
    """Retrieve a filtered Eurostat Statistics API series (no API key required)."""
    url = f"{EUROSTAT_BASE_URL}/{dataset_code}"
    params = {"lang": "EN", "lastTimePeriod": max(1, int(last_n_periods))}
    params.update(filters)
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=45,
        )
        response.raise_for_status()
        return parse_jsonstat_series(response.json(), name=name)
    except Exception as exc:
        # The provider can return 400 for invalid/obsolete filters; keep the daily run alive.
        log.warning(
            "Eurostat dataset %s unavailable: %s",
            dataset_code,
            type(exc).__name__,
        )
        return pd.Series(dtype=float, name=name)


def _latest_snapshot(label: str, series: pd.Series) -> dict:
    return {
        label: float(series.iloc[-1]) if not series.empty else None,
        label + "_date": str(series.index[-1]) if not series.empty else None,
    }


def get_eurostat_snapshot() -> dict:
    """Return latest Belgian and euro-area inflation, unemployment and GDP growth.

    HICP series use the post-2026 ECOICOP v2 dataset. Euro-area geography uses the
    dynamic EA aggregate; Belgium is reported separately for local context.
    """
    specs = [
        (
            "eurostat_hicp_yoy_be",
            "prc_hicp_minr",
            {"freq": "M", "unit": "RCH_A", "coicop18": "TOTAL", "geo": "BE"},
        ),
        (
            "eurostat_hicp_yoy_ea",
            "prc_hicp_minr",
            {"freq": "M", "unit": "RCH_A", "coicop18": "TOTAL", "geo": "EA"},
        ),
        (
            "eurostat_unemployment_be",
            "une_rt_m",
            {"freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT",
             "sex": "T", "geo": "BE"},
        ),
        (
            "eurostat_unemployment_ea21",
            "une_rt_m",
            {"freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT",
             "sex": "T", "geo": "EA21"},
        ),
        (
            "eurostat_gdp_qoq_be",
            "namq_10_gdp",
            {"freq": "Q", "unit": "CLV_PCH_PRE", "s_adj": "SCA",
             "na_item": "B1GQ", "geo": "BE"},
        ),
        (
            "eurostat_gdp_qoq_ea21",
            "namq_10_gdp",
            {"freq": "Q", "unit": "CLV_PCH_PRE", "s_adj": "SCA",
             "na_item": "B1GQ", "geo": "EA21"},
        ),
    ]

    snapshot = {}
    for label, dataset, filters in specs:
        series = get_eurostat_series(dataset, filters, label, last_n_periods=6)
        snapshot.update(_latest_snapshot(label, series))
    return snapshot

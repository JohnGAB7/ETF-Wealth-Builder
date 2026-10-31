import pandas as pd

from src.models.probabilistic import make_training_frame
from src.data.valueinvesting import (
    weighted_constituent_upside,
    eligible_holdings_for_valueinvesting,
)
from src.data.ecb_data import parse_ecb_csv_series
from src.data.eurostat_data import parse_jsonstat_series


def test_forward_target_tail_is_missing():
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    close = pd.Series(range(100, 110), index=idx, dtype=float)
    features = pd.DataFrame({"momentum_21d": [0.1] * 10}, index=idx)
    frame = make_training_frame(features, close, horizon=3)
    assert frame["forward_return"].tail(3).isna().all()
    assert frame["positive_forward_return"].tail(3).isna().all()


def test_only_us_and_canadian_holdings_are_sent_to_valueinvesting():
    holdings = [
        {"ticker": "AAA", "weight": 0.4, "market": "US"},
        {"ticker": "BBB", "weight": 0.2, "market": "Canada"},
        {"ticker": "CCC", "weight": 0.3, "market": "NL"},
        {"ticker": "DDD", "weight": 0.1},
    ]
    eligible = eligible_holdings_for_valueinvesting(holdings)
    assert [row["ticker"] for row in eligible] == ["AAA", "BBB"]


def test_valuation_coverage_is_measured_against_entire_etf():
    payload = {
        "AAA": {"valuation": {"upside_dcf_ebitda_10": 0.2}},
        "BBB": {"valuation": {"upside_dcf_ebitda_10": 0.1}},
    }
    holdings = [
        {"ticker": "AAA", "weight": 0.4, "market": "US"},
        {"ticker": "BBB", "weight": 0.2, "market": "CA"},
        {"ticker": "CCC", "weight": 0.3, "market": "NL"},
        {"ticker": "DDD", "weight": 0.1, "market": "JP"},
    ]
    result = weighted_constituent_upside(payload, holdings)
    assert abs(result["weighted_upside"] - (0.4 * 0.2 + 0.2 * 0.1) / 0.6) < 1e-12
    assert abs(result["coverage_weight"] - 0.6) < 1e-12
    assert abs(result["supported_market_weight"] - 0.6) < 1e-12
    assert abs(result["unsupported_market_weight"] - 0.4) < 1e-12
    assert result["scope"] == "US_AND_CANADA_ONLY"


def test_ecb_csv_parser_reads_dates_and_numeric_observations():
    csv_text = (
        "KEY,FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
        "FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,2026-09-30,2.0\n"
        "FM.D.U2.EUR.4F.KR.DFR.LEV,D,U2,2026-10-01,2.0\n"
    )
    series = parse_ecb_csv_series(csv_text, "deposit_rate")
    assert series.name == "deposit_rate"
    assert list(series.index) == ["2026-09-30", "2026-10-01"]
    assert series.iloc[-1] == 2.0


def test_eurostat_jsonstat_parser_extracts_time_series_from_sparse_payload():
    payload = {
        "id": ["freq", "geo", "time"],
        "size": [1, 1, 3],
        "dimension": {
            "freq": {"category": {"index": {"M": 0}}},
            "geo": {"category": {"index": {"BE": 0}}},
            "time": {"category": {"index": {
                "2026-07": 0, "2026-08": 1, "2026-09": 2
            }}},
        },
        "value": {"0": 2.1, "1": 2.3, "2": 2.5},
    }
    series = parse_jsonstat_series(payload, "be_hicp")
    assert series.name == "be_hicp"
    assert list(series.index) == ["2026-07", "2026-08", "2026-09"]
    assert list(series.values) == [2.1, 2.3, 2.5]


def test_eurostat_jsonstat_parser_handles_non_time_dimensions_before_time():
    payload = {
        "id": ["freq", "unit", "geo", "time"],
        "size": [1, 1, 1, 2],
        "dimension": {
            "freq": {"category": {"index": {"Q": 0}}},
            "unit": {"category": {"index": {"CLV_PCH_PRE": 0}}},
            "geo": {"category": {"index": {"EA": 0}}},
            "time": {"category": {"index": {"2026-Q1": 0, "2026-Q2": 1}}},
        },
        "value": [0.3, -0.1],
    }
    series = parse_jsonstat_series(payload, "ea_gdp_qoq")
    assert series.to_dict() == {"2026-Q1": 0.3, "2026-Q2": -0.1}

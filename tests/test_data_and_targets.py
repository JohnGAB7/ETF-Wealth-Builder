import pandas as pd
from src.models.probabilistic import make_training_frame
from src.data.valueinvesting import (
    weighted_constituent_upside,
    eligible_holdings_for_valueinvesting,
)

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

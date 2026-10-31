import pandas as pd
from src.models.probabilistic import make_training_frame
from src.data.valueinvesting import weighted_constituent_upside

def test_forward_target_tail_is_missing():
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    close = pd.Series(range(100, 110), index=idx, dtype=float)
    features = pd.DataFrame({"momentum_21d": [0.1] * 10}, index=idx)
    frame = make_training_frame(features, close, horizon=3)
    assert frame["forward_return"].tail(3).isna().all()
    assert frame["positive_forward_return"].tail(3).isna().all()

def test_valuation_reports_coverage():
    payload = {"AAA": {"valuation": {"upside_dcf_ebitda_10": 0.2}}}
    holdings = [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}]
    result = weighted_constituent_upside(payload, holdings)
    assert result["weighted_upside"] == 0.2
    assert result["coverage_weight"] == 0.5

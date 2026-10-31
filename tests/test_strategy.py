from src.strategy.opportunity import opportunity_score, classify_signal
from src.portfolio.allocation import suggested_tranche

def test_score_is_bounded():
    score = opportunity_score(prob_positive=0.7, expected_return=0.08,
                              downside_risk=0.2, valuation_gap=0.1,
                              technical_setup=0.8, macro_news=0.6, data_quality=0.9)
    assert 0 <= score <= 100

def test_missing_data_blocks_buy_signal():
    assert classify_signal(90, 0.9, 0.2) == "INSUFFICIENT_EVIDENCE"

def test_tranche_respects_cap():
    amount = suggested_tranche(10000, 90, max_fraction=0.35, daily_cap_eur=2000)
    assert amount <= 2000
    assert amount >= 0

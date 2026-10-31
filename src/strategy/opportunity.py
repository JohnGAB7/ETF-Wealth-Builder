def clamp01(x):
    return max(0.0, min(1.0, float(x)))

def opportunity_score(prob_positive=None, expected_return=None, downside_risk=None,
                      valuation_gap=None, technical_setup=None, macro_news=None,
                      data_quality=0.0) -> float:
    """Transparent 0-100 composite. Missing components are excluded and weights renormalized."""
    components = {
        "probability": (None if prob_positive is None else clamp01(prob_positive), 0.25),
        "expected_return": (None if expected_return is None else clamp01(0.5 + expected_return * 2), 0.15),
        "downside": (None if downside_risk is None else 1 - clamp01(downside_risk), 0.15),
        "valuation": (None if valuation_gap is None else clamp01(0.5 + valuation_gap), 0.20),
        "technical": (None if technical_setup is None else clamp01(technical_setup), 0.10),
        "macro_news": (None if macro_news is None else clamp01(macro_news), 0.10),
        "quality": (clamp01(data_quality), 0.05),
    }
    available = [(v, w) for v, w in components.values() if v is not None]
    if not available:
        return 0.0
    return 100 * sum(v*w for v, w in available) / sum(w for _, w in available)

def classify_signal(score: float, probability: float | None, coverage: float,
                     score_threshold: float = 75, probability_threshold: float = 0.62,
                     min_coverage: float = 0.60) -> str:
    if coverage < min_coverage or probability is None:
        return "INSUFFICIENT_EVIDENCE"
    if score >= score_threshold and probability >= probability_threshold:
        return "BUY_OPPORTUNITY_REVIEW"
    if score >= 55:
        return "WATCH"
    return "REGULAR_DCA"

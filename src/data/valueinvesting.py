import logging
import requests
from src.config import get_secret

log = logging.getLogger(__name__)
BASE_URL = "https://valueinvesting.io/api/valuation"

def get_valuations(tickers: list[str]) -> dict:
    """Fetch up to 50 tickers per request using the documented /api/valuation endpoint."""
    key = get_secret("VALUEINVESTING_API_KEY")
    if not key or not tickers:
        return {}
    result = {}
    session = requests.Session()
    for start in range(0, len(tickers), 50):
        batch = tickers[start:start + 50]
        try:
            response = session.get(
                BASE_URL,
                params={"tickers": ",".join(batch), "api_key": key},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                result.update(payload)
        except Exception as exc:
            # The key is in the query string: never log request URLs or response objects.
            log.warning("ValueInvesting.io request failed (%s tickers): %s",
                        len(batch), type(exc).__name__)
    return result

def weighted_constituent_upside(payload: dict, holdings: list[dict],
                                model: str = "upside_dcf_ebitda_10") -> dict:
    """Return weighted equity-level DCF upside and explicit holdings coverage.

    This is a weighted constituent valuation indicator, NOT an ETF fair value.
    The caller must provide current, dated holdings and understand DCF model limitations.
    """
    weighted_sum, covered_weight = 0.0, 0.0
    for row in holdings:
        ticker, weight = row.get("ticker"), row.get("weight")
        item = payload.get(ticker, {})
        valuation = item.get("valuation", {}) if isinstance(item, dict) else {}
        upside = valuation.get(model)
        try:
            if upside is None or weight is None:
                continue
            w, u = float(weight), float(upside)
            if w < 0:
                continue
            weighted_sum += w * u
            covered_weight += w
        except (TypeError, ValueError):
            continue
    return {
        "weighted_upside": weighted_sum / covered_weight if covered_weight else None,
        "coverage_weight": covered_weight,
        "model": model,
    }

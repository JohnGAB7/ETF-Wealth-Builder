import logging
import time

import requests
from datetime import date, timedelta
from src.config import get_secret

log = logging.getLogger(__name__)

def get_market_news(category: str = "general") -> list[dict]:
    """Optional Finnhub market-news adapter; coverage depends on subscription."""
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": category, "token": key},
            timeout=20,
        )
        r.raise_for_status()
        payload = r.json()
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        log.warning("Finnhub news unavailable: %s", type(exc).__name__)
        return []

# Finnhub free tier: 60 calls/minute. Calls are spaced and memoised per run.
FINNHUB_MIN_INTERVAL_S = 1.1
_RECOMMENDATION_CACHE: dict = {}
_last_call = [0.0]


def get_company_recommendations(symbol: str) -> list[dict]:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []
    if symbol in _RECOMMENDATION_CACHE:
        return _RECOMMENDATION_CACHE[symbol]
    wait = FINNHUB_MIN_INTERVAL_S - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": symbol, "token": key},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        data = data if isinstance(data, list) else []
        _RECOMMENDATION_CACHE[symbol] = data
        return data
    except Exception as exc:
        log.warning("Finnhub recommendations unavailable for %s: %s", symbol, type(exc).__name__)
        return []

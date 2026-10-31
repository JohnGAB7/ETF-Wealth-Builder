import logging
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

def get_company_recommendations(symbol: str) -> list[dict]:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": symbol, "token": key},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("Finnhub recommendations unavailable for %s: %s", symbol, type(exc).__name__)
        return []

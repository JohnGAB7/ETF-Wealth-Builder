import logging
import requests
from src.config import get_secret

log = logging.getLogger(__name__)
BASE_URL = "https://valueinvesting.io/api/valuation"

# This user's current ValueInvesting.io subscription covers US and Canadian equities only.
# We require an explicit market label in holdings files; never infer geography from ticker syntax.
SUPPORTED_MARKETS = {"US", "USA", "UNITED STATES", "CA", "CANADA"}

def normalize_market(value) -> str:
    return str(value or "").strip().upper()

def eligible_holdings_for_valueinvesting(holdings: list[dict]) -> list[dict]:
    """Select only holdings explicitly identified as US or Canadian equities."""
    return [
        row for row in holdings
        if normalize_market(row.get("market")) in SUPPORTED_MARKETS
        and row.get("ticker")
    ]

def get_valuations(tickers: list[str]) -> dict:
    """Fetch up to 50 eligible US/Canadian tickers per documented API request.

    The caller must first apply eligible_holdings_for_valueinvesting(). The API key
    is read from the environment and is never logged or written to a file.
    """
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
    """Return a covered-slice DCF upside and coverage against the entire ETF.

    ValueInvesting.io in this project is limited to US and Canadian holdings. The
    weighted upside is the weighted average of successfully valued eligible names.
    coverage_weight is their weight divided by total ETF holdings weight, not by
    the supported-country slice. This is NOT an ETF fair value.
    """
    weighted_sum, covered_weight = 0.0, 0.0
    eligible_weight, total_weight = 0.0, 0.0
    for row in holdings:
        ticker, weight = row.get("ticker"), row.get("weight")
        try:
            w = float(weight)
            if w <= 0:
                continue
        except (TypeError, ValueError):
            continue
        total_weight += w
        if normalize_market(row.get("market")) not in SUPPORTED_MARKETS:
            continue
        eligible_weight += w
        item = payload.get(ticker, {}) if ticker else {}
        valuation = item.get("valuation", {}) if isinstance(item, dict) else {}
        upside = valuation.get(model)
        try:
            if upside is None:
                continue
            weighted_sum += w * float(upside)
            covered_weight += w
        except (TypeError, ValueError):
            continue

    return {
        "weighted_upside": weighted_sum / covered_weight if covered_weight else None,
        "coverage_weight": covered_weight / total_weight if total_weight else 0.0,
        "supported_market_weight": eligible_weight / total_weight if total_weight else 0.0,
        "coverage_within_supported_markets": (
            covered_weight / eligible_weight if eligible_weight else 0.0
        ),
        "unsupported_market_weight": (
            max(0.0, total_weight - eligible_weight) / total_weight if total_weight else 0.0
        ),
        "covered_weight_raw": covered_weight,
        "total_holdings_weight_raw": total_weight,
        "model": model,
        "scope": "US_AND_CANADA_ONLY",
    }

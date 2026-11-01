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

# Per-run memo: the same constituents (Apple, Microsoft...) appear in several ETFs;
# each ticker is requested at most once per process.
_VALUATION_CACHE: dict = {}


def get_valuations(tickers: list[str]) -> dict:
    """Fetch up to 50 eligible US/Canadian tickers per documented API request.

    The caller must first apply eligible_holdings_for_valueinvesting(). The API key
    is read from the environment and is never logged or written to a file.
    """
    key = get_secret("VALUEINVESTING_API_KEY")
    if not key or not tickers:
        return {}
    wanted = list(dict.fromkeys(tickers))
    missing = [t for t in wanted if t not in _VALUATION_CACHE]
    result = {}
    session = requests.Session()
    for start in range(0, len(missing), 50):
        batch = missing[start:start + 50]
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
            # Only a successful request is memoised; a ticker absent from the answer
            # is remembered as absent so it is not asked again in the same run.
            for ticker in batch:
                _VALUATION_CACHE[ticker] = payload.get(ticker) if isinstance(payload, dict) else None
        except Exception as exc:
            # The key is in the query string: never log request URLs or response objects.
            log.warning("ValueInvesting.io request failed (%s tickers): %s",
                        len(batch), type(exc).__name__)
    for ticker in wanted:
        if ticker not in result and _VALUATION_CACHE.get(ticker) is not None:
            result[ticker] = _VALUATION_CACHE[ticker]
    return result

# |upside| above this (300 %) is treated as implausible for a DCF upside expressed
# as a fraction. Such values are excluded and counted, never rescaled: if the API
# ever returned percentages, coverage would visibly fall to zero instead of the
# score silently saturating.
MAX_ABS_UPSIDE = 3.0


def weighted_constituent_upside(payload: dict, holdings: list[dict],
                                model: str = "upside_dcf_ebitda_10",
                                etf_total_weight: float = 1.0,
                                max_abs_upside: float = MAX_ABS_UPSIDE) -> dict:
    """Return a covered-slice DCF upside and coverage against the entire ETF.

    ValueInvesting.io in this project is limited to US and Canadian holdings. The
    weighted upside is the weighted average of successfully valued eligible names.
    `holdings` weights are fractions of the whole ETF (see src.data.holdings); a
    partial file is not rescaled. Every coverage ratio is divided by
    max(etf_total_weight, sum of file weights), i.e. by the whole ETF. This is NOT
    an ETF fair value.
    """
    weighted_sum, covered_weight = 0.0, 0.0
    eligible_weight, file_weight = 0.0, 0.0
    implausible = 0
    for row in holdings:
        ticker, weight = row.get("ticker"), row.get("weight")
        try:
            w = float(weight)
            if w <= 0:
                continue
        except (TypeError, ValueError):
            continue
        file_weight += w
        if normalize_market(row.get("market")) not in SUPPORTED_MARKETS:
            continue
        eligible_weight += w
        item = payload.get(ticker, {}) if ticker else {}
        valuation = item.get("valuation", {}) if isinstance(item, dict) else {}
        upside = valuation.get(model)
        try:
            if upside is None:
                continue
            value = float(upside)
        except (TypeError, ValueError):
            continue
        if value != value or abs(value) > max_abs_upside:
            implausible += 1
            continue
        weighted_sum += w * value
        covered_weight += w

    if implausible:
        log.warning("ValueInvesting.io: %s implausible upside value(s) excluded "
                    "(|upside| > %.0f%%); check the API unit", implausible, max_abs_upside * 100)
    total_weight = max(float(etf_total_weight or 0.0), file_weight)
    return {
        "weighted_upside": weighted_sum / covered_weight if covered_weight else None,
        "coverage_weight": covered_weight / total_weight if total_weight else 0.0,
        "supported_market_weight": eligible_weight / total_weight if total_weight else 0.0,
        "coverage_within_supported_markets": (
            covered_weight / eligible_weight if eligible_weight else 0.0
        ),
        # Share of the ETF that is in a supported market *and* listed in the file
        # is supported_market_weight; the rest of the ETF is either in another
        # market or simply absent from a partial holdings file.
        "unsupported_market_weight": (
            (file_weight - eligible_weight) / total_weight if total_weight else 0.0
        ),
        "holdings_file_weight": file_weight / total_weight if total_weight else 0.0,
        "implausible_upside_count": implausible,
        "covered_weight_raw": covered_weight,
        "total_holdings_weight_raw": file_weight,
        "etf_total_weight": total_weight,
        "model": model,
        "scope": "US_AND_CANADA_ONLY",
    }

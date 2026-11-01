from src.data.news_data import get_company_recommendations

# Only the largest lines are queried: a 3 000-line small-cap file would otherwise
# mean 3 000 API calls per run. Coverage stays measured against the whole ETF,
# so a smaller sample shows up as a lower analyst_coverage_weight, never hidden.
MAX_ANALYST_CONSTITUENTS = 25


def aggregate_recommendations(holdings: list[dict],
                              max_constituents: int = MAX_ANALYST_CONSTITUENTS) -> dict:
    """Aggregate analyst recommendations over dated ETF holdings.

    `holdings`: rows with ticker and decimal weight. Finnhub recommendation endpoint
    returns monthly Buy/Hold/Sell buckets; this adapter averages the latest available
    row per constituent, weighted by holdings weight. Coverage is reported explicitly.
    """
    totals = {"buy": 0.0, "hold": 0.0, "sell": 0.0}
    covered_weight = 0.0
    def _weight(row):
        try:
            return float(row.get("weight") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    largest = sorted(holdings, key=_weight, reverse=True)[:max_constituents]
    for holding in largest:
        ticker, weight = holding.get("ticker"), holding.get("weight")
        if not ticker or weight is None:
            continue
        rows = get_company_recommendations(ticker)
        if not rows:
            continue
        latest = rows[0]
        try:
            covered_weight += float(weight)
            totals["buy"] += float(latest.get("buy", 0)) * float(weight)
            totals["hold"] += float(latest.get("hold", 0)) * float(weight)
            totals["sell"] += float(latest.get("sell", 0)) * float(weight)
        except (TypeError, ValueError):
            continue
    return {
        "weighted_buy": totals["buy"],
        "weighted_hold": totals["hold"],
        "weighted_sell": totals["sell"],
        "analyst_coverage_weight": covered_weight,
        "analyst_constituents_queried": len(largest),
    }

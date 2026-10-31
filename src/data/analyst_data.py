from src.data.news_data import get_company_recommendations

def aggregate_recommendations(holdings: list[dict]) -> dict:
    """Aggregate analyst recommendations over dated ETF holdings.

    `holdings`: rows with ticker and decimal weight. Finnhub recommendation endpoint
    returns monthly Buy/Hold/Sell buckets; this adapter averages the latest available
    row per constituent, weighted by holdings weight. Coverage is reported explicitly.
    """
    totals = {"buy": 0.0, "hold": 0.0, "sell": 0.0}
    covered_weight = 0.0
    for holding in holdings:
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
    }

import argparse
import logging
import pandas as pd
from src.config import load_yaml, ROOT
from src.logging_config import configure_logging
from src.data.market_data import get_history
from src.data.macro_data import get_macro_snapshot
from src.data.news_data import get_market_news
from src.data.valueinvesting import (
    get_valuations, weighted_constituent_upside, eligible_holdings_for_valueinvesting,
)
from src.data.analyst_data import aggregate_recommendations
from src.features.technical import build_technical_features
from src.features.news import summarize_news
from src.models.probabilistic import make_training_frame, fit_predict
from src.strategy.opportunity import opportunity_score, classify_signal
from src.reporting.report import write_report
from src.notifications.email_alert import send_email, send_digest

log = logging.getLogger("etf_wealth_builder")

def load_holdings(path):
    file_path = ROOT / path
    if not file_path.exists():
        return []
    try:
        frame = pd.read_csv(file_path)
        if not {"ticker", "weight"}.issubset(frame.columns):
            log.warning("Holdings file %s must contain ticker,weight", path)
            return []
        frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
        frame = frame.dropna(subset=["ticker", "weight"])
        total = frame["weight"].sum()
        if total > 1.5:  # likely percentage weights
            frame["weight"] = frame["weight"] / 100.0
        total = frame["weight"].sum()
        if total <= 0:
            return []
        frame["weight"] = frame["weight"] / total
        return frame.to_dict("records")
    except Exception as exc:
        log.warning("Could not read holdings %s: %s", path, type(exc).__name__)
        return []

def run_once():
    universe = load_yaml("config/etf_universe.yaml")["etfs"]
    strategy = load_yaml("config/strategy.yaml")
    macro = get_macro_snapshot()
    news_items = get_market_news()
    news = summarize_news(news_items)
    results = []

    for etf in [x for x in universe if x.get("enabled", True)]:
        symbol = etf["yahoo_symbol"]
        history = get_history(symbol)
        if history.empty or len(history) < 220:
            results.append({"id": etf["id"], "status": "INSUFFICIENT_PRICE_HISTORY"})
            continue

        features = build_technical_features(history)
        # Latest macro/news are used only in the current decision layer, not backfilled
        # across historical rows. Historical ML needs archived point-in-time releases.
        frame = make_training_frame(features, history["Close"],
                                    strategy["primary_horizon_days"])
        model_result = fit_predict(frame, strategy["minimum_training_rows"])

        holdings = load_holdings(etf.get("constituents_file", ""))
        valuation_holdings = eligible_holdings_for_valueinvesting(holdings)
        tickers = [h["ticker"] for h in valuation_holdings]
        valuation_payload = get_valuations(tickers) if tickers else {}
        valuation_result = weighted_constituent_upside(valuation_payload, holdings)
        valuation_gap = valuation_result.get("weighted_upside")
        valuation_coverage = float(valuation_result.get("coverage_weight", 0.0) or 0.0)
        analyst = aggregate_recommendations(holdings) if holdings else {
            "weighted_buy": 0.0, "weighted_hold": 0.0, "weighted_sell": 0.0,
            "analyst_coverage_weight": 0.0,
        }

        if model_result.get("status") != "MODEL_ESTIMATE":
            result = {"id": etf["id"], "name": etf["name"], **model_result}
        else:
            latest = features.iloc[-1]
            rsi_value = latest.get("rsi14")
            drawdown = latest.get("drawdown")
            technical = 0.5
            if pd.notna(rsi_value):
                technical += max(-0.25, min(0.25, (40 - float(rsi_value)) / 80))
            if pd.notna(drawdown):
                technical += max(-0.15, min(0.15, -float(drawdown)))

            news_component = None
            if news["news_sentiment"] is not None:
                news_component = max(0.0, min(1.0, 0.5 + news["news_sentiment"] / 2))
            if analyst["analyst_coverage_weight"] > 0:
                total_rec = analyst["weighted_buy"] + analyst["weighted_hold"] + analyst["weighted_sell"]
                analyst_component = (
                    (analyst["weighted_buy"] + 0.5 * analyst["weighted_hold"]) / total_rec
                    if total_rec > 0 else None
                )
                if analyst_component is not None:
                    news_component = analyst_component if news_component is None else (
                        0.5 * news_component + 0.5 * analyst_component
                    )

            score = opportunity_score(
                prob_positive=model_result["prob_positive"],
                expected_return=model_result["expected_return"],
                downside_risk=None, valuation_gap=valuation_gap,
                technical_setup=technical, macro_news=news_component,
                data_quality=0.65 + 0.15 * max(0.0, min(1.0, valuation_coverage)),
            )
            macro_keys = [key for key in macro if not key.endswith("_date")]
            macro_coverage = (
                sum(macro.get(key) is not None for key in macro_keys) / len(macro_keys)
                if macro_keys else 0.0
            )
            news_coverage = float(news.get("news_coverage", 0.0) or 0.0)
            analyst_coverage = float(analyst.get("analyst_coverage_weight", 0.0) or 0.0)
            # Core price/model evidence contributes 45%; optional evidence contributes
            # only in proportion to real observed coverage. Missing feeds cannot inflate it.
            coverage = (
                0.45
                + 0.15 * max(0.0, min(1.0, valuation_coverage))
                + 0.10 * max(0.0, min(1.0, analyst_coverage))
                + 0.15 * max(0.0, min(1.0, news_coverage))
                + 0.15 * max(0.0, min(1.0, macro_coverage))
            )
            signal = classify_signal(
                score, model_result["prob_positive"], coverage=coverage,
                score_threshold=strategy["opportunity_score_threshold"],
                probability_threshold=strategy["probability_buy_threshold"],
                min_coverage=strategy["minimum_data_coverage"],
            )
            result = {
                "id": etf["id"], "name": etf["name"], "isin": etf["isin"],
                "symbol": symbol, "as_of": str(history.index[-1]),
                "price": float(history["Close"].iloc[-1]),
                "drawdown": float(latest["drawdown"]),
                "rsi14": float(latest["rsi14"]),
                "valuation_weighted_upside": valuation_gap,
                "valuation_coverage_weight": valuation_coverage,
                "valuation_supported_market_weight": valuation_result.get("supported_market_weight", 0.0),
                "valuation_unsupported_market_weight": valuation_result.get("unsupported_market_weight", 0.0),
                "valuation_scope": valuation_result.get("scope", "US_AND_CANADA_ONLY"),
                "analyst": analyst, "news": news,
                "macro_snapshot": macro,
                "score": round(score, 1), "signal": signal,
                **model_result,
            }
            if signal == "BUY_OPPORTUNITY_REVIEW":
                body = (
                    f"ETF Wealth Builder — signal à examiner\\n\\n"
                    f"{etf['name']} ({etf['isin']})\\nTicker: {symbol}\\n"
                    f"Prix observé: {result['price']:.4f}\\nScore: {score:.1f}/100\\n"
                    f"Probabilité estimée de rendement positif à {strategy['primary_horizon_days']} jours: "
                    f"{model_result['prob_positive']:.1%}\\n"
                    f"Rendement conditionnel estimé: {model_result['expected_return']:.2%}\\n"
                    f"Drawdown: {result['drawdown']:.2%}\\n"
                    f"Upside DCF pondéré (poche US/Canada couverte): {valuation_gap}; couverture totale ETF: {valuation_coverage:.1%}\\n"
                    f"Couverture analystes pondérée: {analyst['analyst_coverage_weight']:.1%}\\n\\n"
                    "Signal de recherche uniquement. Vérifier les données, les frais, la fiscalité, "
                    "les liquidités et l'allocation avant toute décision."
                )
                send_email(f"ETF Wealth Builder | Opportunité à examiner | {etf['id']}", body)

        results.append(result)

    report = {"macro_snapshot": macro, "news_summary": news, "etfs": results}
    path = write_report(report)
    # Both notification modes selected: immediate signal emails + one daily digest.
    from datetime import datetime, timezone
    send_digest(results, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    log.info("Report written to %s", path)
    for item in results:
        log.info("%s | %s | %s", item.get("id"), item.get("signal", item.get("status")), item.get("score"))
    return report

if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one monitoring cycle")
    args = parser.parse_args()
    run_once()

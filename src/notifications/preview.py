"""Generate HTML and plain-text e-mail previews from fictitious data.

Usage:
    python -m src.notifications.preview            # writes to data/previews/
    python -m src.notifications.preview --out DIR

Nothing is sent and no network call is made. All values below are invented for
visual checks only; they are not market data and not research results.
"""
import argparse
from pathlib import Path

from src.config import ROOT, load_yaml
from src.notifications.email_alert import compose_digest, compose_signal_alert

RUN_DATE = "2026-10-30"

_VALIDATION_OK = {"brier": 0.221, "brier_reference": 0.236, "auc": 0.61,
                  "test_rows": 540, "test_start": "2024-08-01", "test_end": "2026-08-03"}
_VALIDATION_WEAK = {"brier": 0.252, "brier_reference": 0.236, "auc": 0.47,
                    "test_rows": 540, "test_start": "2024-08-01", "test_end": "2026-08-03"}

MACRO_FULL = {
    "ecb_deposit_facility_rate": 2.0, "ecb_deposit_facility_rate_date": "2026-10-29",
    "ecb_usd_per_eur": 1.1642, "ecb_usd_per_eur_date": "2026-10-29",
    "eurostat_hicp_yoy_be": 2.4, "eurostat_hicp_yoy_be_date": "2026-09",
    "eurostat_hicp_yoy_ea": 2.1, "eurostat_hicp_yoy_ea_date": "2026-09",
    "eurostat_unemployment_be": 5.9, "eurostat_unemployment_be_date": "2026-09",
    "eurostat_unemployment_ea21": 6.3, "eurostat_unemployment_ea21_date": "2026-09",
    "eurostat_gdp_qoq_be": 0.3, "eurostat_gdp_qoq_be_date": "2026-Q2",
    "eurostat_gdp_qoq_ea21": 0.2, "eurostat_gdp_qoq_ea21_date": "2026-Q2",
    "us_policy_rate": 3.88, "us_policy_rate_date": "2026-09-01",
    "us_cpi_index": 324.1, "us_cpi_index_date": "2026-09-01",
    "us_unemployment": 4.3, "us_unemployment_date": "2026-09-01",
    "us_10y_yield": 4.12, "us_10y_yield_date": "2026-10-28",
    "us_10y_2y_spread": 0.55, "us_10y_2y_spread_date": "2026-10-28",
    "us_high_yield_spread": 3.05, "us_high_yield_spread_date": "2026-10-28",
}
MACRO_PARTIAL = {k: v for k, v in MACRO_FULL.items() if not k.startswith("us_")}


def _etf(**overrides):
    base = {
        "id": "vwce", "name": "Vanguard FTSE All-World UCITS ETF", "isin": "IE00BK5BQT80",
        "symbol": "VWCE.DE", "currency": "EUR", "horizon_days": 63, "as_of": RUN_DATE,
        "price": 138.25, "drawdown": -0.081, "rsi14": 41.0, "signal": "WATCH",
        "score": 62.5, "prob_positive": 0.64, "expected_return": 0.035,
        "base_rate_positive": 0.68, "validation": _VALIDATION_WEAK, "rows": 1650,
        "data_coverage": 0.82, "valuation_coverage_weight": 0.34,
        "valuation_weighted_upside": 0.07, "analyst": {"analyst_coverage_weight": 0.0},
    }
    base.update(overrides)
    return base


def scenarios() -> dict:
    review = _etf(id="cspx", name="iShares Core S&P 500 UCITS ETF", isin="IE00B5BMR087",
                  symbol="CSPX.L", currency="USD", price=612.4, drawdown=-0.06, rsi14=33.0,
                  signal="BUY_OPPORTUNITY_REVIEW", score=78.0, prob_positive=0.71,
                  expected_return=0.045, base_rate_positive=0.70, validation=_VALIDATION_OK,
                  data_coverage=0.75, valuation_coverage_weight=0.0,
                  valuation_weighted_upside=None)
    watch = _etf()
    regular = _etf(id="iwda", name="iShares Core MSCI World UCITS ETF", isin="IE00B4L5Y983",
                   symbol="IWDA.AS", price=104.1, drawdown=-0.02, rsi14=58.0,
                   signal="REGULAR_DCA", score=48.0, prob_positive=0.58,
                   expected_return=0.012, base_rate_positive=0.69)
    insufficient = {"id": "eimi", "name": "iShares Core MSCI Emerging Markets IMI UCITS ETF",
                    "isin": "IE00BKM4GZ66", "symbol": "EIMI.L", "currency": "USD",
                    "horizon_days": 63, "status": "INSUFFICIENT_EVIDENCE", "rows": 310}
    no_history = {"id": "eimi", "name": "iShares Core MSCI Emerging Markets IMI UCITS ETF",
                  "isin": "IE00BKM4GZ66", "symbol": "EIMI.L", "currency": "USD",
                  "horizon_days": 63, "status": "INSUFFICIENT_PRICE_HISTORY"}
    stale = _etf(as_of="2026-10-20")
    return {
        "digest_opportunity": ([review, watch, regular, insufficient], MACRO_FULL),
        "digest_calm": ([regular, _etf(signal="REGULAR_DCA", score=51.0)], MACRO_FULL),
        "digest_degraded": ([stale, no_history], MACRO_PARTIAL),
        "digest_empty": ([], {}),
        "alert_opportunity": review,
    }


def write_previews(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        strategy = load_yaml("config/strategy.yaml")
    except OSError:
        strategy = None
    written = []
    for name, payload in scenarios().items():
        if name.startswith("alert"):
            subject, text, html = compose_signal_alert(payload, 63, strategy, RUN_DATE)
        else:
            results, macro = payload
            subject, text, html = compose_digest(results, RUN_DATE, macro, strategy)
        (out_dir / f"{name}.html").write_text(html, encoding="utf-8")
        (out_dir / f"{name}.txt").write_text(f"Objet : {subject}\n\n{text}", encoding="utf-8")
        written += [out_dir / f"{name}.html", out_dir / f"{name}.txt"]
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "data" / "previews"))
    args = parser.parse_args(argv)
    for path in write_previews(Path(args.out)):
        print(path)


if __name__ == "__main__":
    main()

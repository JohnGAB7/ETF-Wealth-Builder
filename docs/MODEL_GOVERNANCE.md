# Model governance and validation checklist

## Target and leakage control
- Target: ETF adjusted total return over 21/63/126 trading days.
- Use adjusted prices and include distributions.
- Preserve publication timestamps for macro releases, analyst changes and news.
- Use point-in-time constituents and historical weights, not today's holdings backfilled.
- Use ALFRED vintages or archived release snapshots for revised macro data.
- Purge overlapping forward-return labels at split boundaries and add an embargo.
- Use nested expanding/rolling walk-forward validation, never random splitting.

## Required benchmarks and metrics
- Compare with unconditional historical base rate, logistic regression, buy-and-hold,
  and classic monthly DCA.
- Report Brier score, log loss, calibration curve, ROC-AUC, precision at alert threshold,
  hit rate, expected return, max drawdown, turnover and cash drag.
- Include fees, bid/ask spread, FX, withholding taxes and Belgian TOB/tax assumptions.
- Test several market regimes and conduct sensitivity analysis.

## Signal governance
- Never equate a probability of positive return with a guaranteed profit.
- Never alert BUY if data are stale, coverage is insufficient or model validation fails.
- Keep probability calibration separate by ETF and forecast horizon where sample size permits.
- Log data timestamps, model version, features, score, reason codes and email outcome.
- Monitor drift and provider outages; fail closed when critical data are missing.

## Known limitations of this starter
The current model is a technical-feature baseline with chronological holdout and
time-series calibration. It is not yet nested, purged or embargoed, and its reported
metrics are preliminary. The macro/news snapshots are not backfilled into historical
training rows. Do not claim that the model has discovered a profitable strategy until
a rigorous out-of-sample backtest and paper-trading period support that conclusion.

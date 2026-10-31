# Model governance and validation checklist

## Target and leakage control

- Target: ETF adjusted total return over 21/63/126 trading days.
- Use adjusted prices and include distributions.
- Preserve publication timestamps for macro releases, analyst changes and news.
- Use point-in-time constituents and historical weights, not today's holdings backfilled.
- Use ALFRED vintages or archived release snapshots for revised macro data.
- Purge overlapping forward-return labels at split boundaries and add an embargo.
- Use nested expanding/rolling walk-forward validation, never random splitting.

## Macro data source limitations

- FRED requires a free API key; its latest observations can be revised. Archive ALFRED vintages for point-in-time historical reconstruction.
- ECB Data Portal exposes public SDMX observations and supports historical observation versions through its API, but this starter currently fetches the latest observations only.
- Eurostat's public Statistics API serves the latest dataset version and does not provide historical dataset vintages. Archive each scheduled snapshot with retrieval timestamp and observation period before using macro data in historical model training.
- Latest ECB and Eurostat values are currently contextual report data; they are not backfilled across historical training rows.
- Daily report artifacts are retained for 90 days only. This temporary retention does not replace a long-term, versioned macro data store.

## Geographic coverage of fundamental valuation

- The configured ValueInvesting.io subscription covers US and Canadian equities only.
- Never send constituents from other markets to this API. Require an explicit market field in holdings files.
- Calculate fundamental valuation coverage against total ETF weight; report the supported-market share and the successfully valued share separately.
- A weighted DCF upside on the covered subset is a partial constituent indicator, not an ETF fair value.
- If coverage is low, do not describe the fundamental signal as representative of the entire ETF.
- Holdings weights are never renormalized; partial files keep their real share of the ETF.
- DCF upside values with |upside| > 300 % are excluded as implausible and counted (unit check), never rescaled.

## Freshness

- A review signal is blocked (INSUFFICIENT_EVIDENCE) when the last price is older than `max_price_age_days` (strategy.yaml, default 5 calendar days).
- Macro observations older than 10 days (daily), 100 days (monthly) or 240 days (quarterly) after the start of their period are flagged as old in reports; they are not removed or replaced.
- Each report records its UTC retrieval timestamp (`retrieved_at`).

## Required benchmarks and metrics

- Compare with unconditional historical base rate, logistic regression, buy-and-hold, and classic monthly DCA.
- Report Brier score, log loss, calibration curve, ROC-AUC, precision at alert threshold, hit rate, expected return, max drawdown, turnover and cash drag.
- Include fees, bid/ask spread, FX, withholding taxes and Belgian TOB/tax assumptions.
- Test several market regimes and conduct sensitivity analysis.

## Signal governance

- Never equate a probability of positive return with a guaranteed profit.
- Never alert BUY if data are stale, coverage is insufficient or model validation fails.
- Keep probability calibration separate by ETF and forecast horizon where sample size permits.
- Log data timestamps, model version, features, score, reason codes and email outcome.
- Monitor drift and provider outages; fail closed when critical data are missing.

## Known limitations of this starter

The current model is a technical-feature baseline with chronological holdout and time-series calibration. It is not yet nested, purged or embargoed, and its reported metrics are preliminary. Macro and news snapshots are not backfilled into historical training rows. Do not claim that the model has discovered a profitable strategy until a rigorous out-of-sample backtest and paper-trading period support that conclusion.

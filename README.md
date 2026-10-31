# ETF Wealth Builder

A research and decision-support platform for long-term ETF investing using a disciplined modified DCA approach.

## Investment policy

- Monthly contribution baseline: EUR 500.
- Hybrid budget: accumulate monthly contributions and allow optional exceptional contributions from the investor's cash reserve.
- Human-in-the-loop: the system produces research signals and email reports; it never places orders.
- Data providers: ValueInvesting.io (existing paid subscription, US and Canada equities only) plus free/public sources where available.\n- ValueInvesting.io constituent valuation coverage is explicitly partial for global ETFs and is measured against total ETF weight.
- No additional paid API subscriptions are assumed.

## Important status

This repository is being initialized. The project is a research scaffold, not a validated investment product. Models, signals, backtests and data pipelines must be independently tested before they are used to inform real investment decisions. No result or signal guarantees a return.

## Security

Never commit API keys, passwords, SMTP credentials, account identifiers or personal financial data. Store credentials only in GitHub Actions Secrets or an equivalent secret manager. Do not paste secrets into issues, pull requests or chat messages.

## Planned components

- Market and ETF price data ingestion.
- ETF holdings ingestion with dated snapshots and data provenance.
- Fundamental valuation aggregation for ETF constituents (not a certified intrinsic value for the ETF itself).
- Macroeconomic and news context with publication timestamps.
- Technical and quantitative features.
- Probabilistic opportunity scoring with time-series validation and calibration.
- Modified DCA allocation ledger, risk limits and audit trail.
- Daily digest and high-priority notifications.
- Automated tests and reproducible research.

## Development principles

1. Point-in-time data only for historical evaluation; record observation and publication/release timestamps.
2. Use walk-forward validation, purge/embargo where labels overlap, and benchmark against simple DCA.
3. Include fees, spreads, FX and relevant Belgian taxes in backtests where applicable.
4. Report data coverage and uncertainty; fail safely when critical inputs are missing.
5. No automatic trading or broker credentials.

## Getting started

The setup instructions will be added alongside the first executable project scaffold.

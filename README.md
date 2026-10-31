# ETF Wealth Builder

A research and decision-support platform for long-term ETF investing using a disciplined modified DCA approach.

## Investment policy

- Monthly contribution baseline: EUR 500.
- Hybrid budget: accumulate monthly contributions and allow optional exceptional contributions from the investor's cash reserve.
- Human-in-the-loop: the system produces research signals and email reports; it never places orders.
- ValueInvesting.io: existing paid subscription, restricted in this project to US and Canadian equities.
- Free macro sources: FRED (API key required), ECB Data Portal (no key), and Eurostat (no key).
- No additional paid API subscriptions are assumed.

## Geographic valuation limitation

ValueInvesting.io is used only for constituents explicitly labelled US or CA in the holdings file. The weighted DCF upside is calculated over the successfully valued supported subset; its coverage is measured against total ETF weight. This is a partial constituent indicator, not a fair value for a global ETF.

## Macro data sources

- FRED: US policy rates, CPI, unemployment, Treasury yields and credit spreads. A free API key is required.
- ECB Data Portal: euro-area deposit facility rate and EUR/USD reference exchange rate. Public SDMX API; no API key.
- Eurostat: Belgian and euro-area HICP inflation, unemployment and quarterly GDP growth. Public Statistics API; no API key.

ECB and Eurostat snapshots currently provide the latest observations for daily research reports. They are not backfilled into historical model rows. Eurostat's Statistics API serves the latest dataset version and does not provide historical dataset vintages, so point-in-time backtests must archive releases separately.

## Important status

This repository is an experimental research scaffold, not a validated investment product. Models, signals, backtests and data pipelines must be independently tested before they are used to inform real investment decisions. No result or signal guarantees a return.

## Security

Never commit API keys, passwords, SMTP credentials, account identifiers or personal financial data. Store credentials only in GitHub Actions Secrets or an equivalent secret manager. Do not paste secrets into issues, pull requests or chat messages.

## Development principles

1. Point-in-time data only for historical evaluation; record observation and publication/release timestamps.
2. Use point-in-time constituents and historical weights, not today's holdings backfilled.
3. Use walk-forward validation, purge/embargo where labels overlap, and benchmark against simple DCA.
4. Include fees, spreads, FX and relevant Belgian taxes in backtests where applicable.
5. Report data coverage and uncertainty; fail safely when critical inputs are missing.
6. No automatic trading or broker credentials.

## Setup

See [docs/SETUP_GITHUB.md](docs/SETUP_GITHUB.md) for GitHub Actions secrets and first-run instructions.

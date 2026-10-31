# GitHub Actions setup checklist

## Secrets to add

In Settings → Secrets and variables → Actions, create:

- `VALUEINVESTING_API_KEY`: your existing ValueInvesting.io key. This subscription is used only for US and Canadian constituents.
- `FRED_API_KEY`: free FRED API key. Optional in the code, but required for the US macro indicators.
- `FINNHUB_API_KEY`: optional; use only if you have a free-tier key and want news/analyst data.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
- `EMAIL_FROM`, `EMAIL_TO`

**No secrets are needed for ECB Data Portal or Eurostat.** Their public data APIs are called directly by the Python modules.

For Gmail SMTP, use `smtp.gmail.com`, port `587`, STARTTLS, and a Google App Password when 2-Step Verification is enabled. Do not use your normal Google password.

## FRED key

Register for a free FRED account and request an API key for the application `ETF Wealth Builder`. Store the key only as the GitHub Actions secret `FRED_API_KEY`. Never add it to `.env.example`, source code, commits or chat messages.

## ETF holdings files

Add dated holdings CSVs under `data/constituents/`. Required columns:

- `ticker`
- `weight`
- `market` (explicit market code such as US, CA, NL, JP)

Only `US` and `CA` rows are sent to ValueInvesting.io. Other markets and rows with missing market labels are excluded. The current repo contains a schema example, not actual constituent holdings.

Use official ETF issuer files and preserve each file's as-of date and source. The starter does not automatically discover or backfill all historical holdings.

## First run

1. Add the secrets above.
2. Upload dated holdings files for the ETF share classes you want to analyze.
3. Open Actions → ETF Wealth Builder — daily monitor → Run workflow manually.
4. Check the workflow logs and inbox. Confirm market data, macro coverage, ValueInvesting coverage and email delivery.
5. Only then rely on the scheduled workflow for recurring research reports.

The workflow uses UTC cron. GitHub Actions scheduled jobs can start late. It is not suitable for intraday execution or guaranteed delivery. Do not commit `.env` or data exports containing licensed/restricted data.

# GitHub deployment checklist

1. Create a **private** GitHub repository named `ETF-Wealth-Builder`.
2. Upload/push the contents of this folder (not the ZIP itself).
3. In Settings → Secrets and variables → Actions, create:
   - `VALUEINVESTING_API_KEY`
   - `FINNHUB_API_KEY` (optional)
   - `FRED_API_KEY` (optional)
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
   - `EMAIL_FROM`, `EMAIL_TO`
4. For Gmail SMTP, use `smtp.gmail.com`, port `587`, STARTTLS, and a Google App Password
   when 2-Step Verification is enabled. Do not use your normal Google password.
5. Add dated holdings CSVs under `data/constituents/`. The starter does not automatically
   discover all holdings. Use the official ETF issuer files or a licensed data source.
6. Run Actions → ETF Wealth Builder — daily monitor → Run workflow manually.
7. Check logs and inbox. Only then enable the scheduled workflow.

The workflow uses UTC cron. GitHub Actions scheduled jobs can start late. It is not
suitable for intraday execution or guaranteed delivery. Do not commit `.env` or data
exports containing licensed/restricted data.

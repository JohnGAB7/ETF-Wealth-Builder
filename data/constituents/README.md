# ETF constituents

Place dated holdings files here. Required CSV columns:

- ticker: constituent equity ticker accepted by the selected data provider
- weight: portfolio weight in the WHOLE ETF, as a fraction (0.025) or a percentage (2.5).
  Weights are never rescaled: a partial file (e.g. top 200 lines = 45 % of the fund) keeps
  a total of 0.45, so coverage stays measured against the entire ETF.
- market: explicit country/market label used to gate ValueInvesting.io requests

For ValueInvesting.io, only rows with market US/USA/United States or CA/Canada are sent
to the API. All other markets and rows with a missing market label are excluded from
ValueInvesting.io requests. Do not infer a market from the ticker suffix.

Example:

```csv
ticker,weight,market
MSFT,0.045,US
SHOP,0.012,CA
ASML,0.009,NL
TSM,0.018,TW
```

Weights sum to 1.0 (100) for a complete file and to less for a partial file. A sum above
1.02 is flagged as inconsistent. Use issuer holdings files or a licensed data provider.

Add a companion metadata file named `<file stem>.meta.yaml` (e.g. `vwce_constituents.meta.yaml`):

```yaml
as_of: 2026-09-30        # holdings date published by the issuer
source: Vanguard website
weight_unit: percent     # or fraction; inferred (max weight > 1 => percent) if absent
```

The as-of date and source are shown in the e-mail. Do not assume current holdings
represent historical holdings.

## Updating from issuer downloads

`src/data/holdings_import.py` converts the raw issuer files (keep the raw files out of
the repository; only the converted CSV and its `.meta.yaml` are committed):

```bash
# iShares CSV (IWDA = SWDA file, CSPX, IUSN = WSML file, SEC0 = SEMI file)
python -m src.data.holdings_import ishares SWDA_holdings.csv --id iwda
# SSGA xlsx: no ticker in the file, tickers are copied from iShares files of the same date
python -m src.data.holdings_import ssga holdings-daily-emea-en-spyl-gy.xlsx --id spyl \
    --ticker-ref CSPX_holdings.csv --ticker-ref SWDA_holdings.csv \
    --ticker-ref WSML_holdings.csv --ticker-ref SEMI_holdings.csv
```

Converted columns: `ticker, weight, market, name, isin, location, exchange, ticker_source`.

- Only equity lines are kept. Cash, FX, futures and money-market lines are dropped and
  are not redistributed: the file total stays slightly below 100 %.
- `market` is `US` / `CA` only when the company's country AND its listing venue are
  US / Canadian. A Dutch company listed on NASDAQ keeps `Netherlands`.
- SSGA lines get a ticker only when an iShares line of the same date has the same country,
  the same price (after a per-country currency factor) and a similar name
  (`ticker_source = ishares_match`). Otherwise the ISIN is kept as identifier
  (`ticker_source = isin`) and no provider values that line. Nothing is guessed.
- iShares tickers are kept as published (e.g. `BRK B`); a provider may not recognise
  some of them, which then simply lowers the reported coverage.

Refresh at least quarterly; the `as_of` date is shown in the e-mail.

## Interpretation

The weighted DCF upside is calculated only on constituents that are both in the US/Canada
subscription scope and successfully returned by ValueInvesting.io. The coverage percentage
is measured against the entire ETF, not just the supported-country subset. It is a
partial constituent valuation indicator, never a certified fair value for the ETF.

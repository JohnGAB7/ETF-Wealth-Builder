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

## Interpretation

The weighted DCF upside is calculated only on constituents that are both in the US/Canada
subscription scope and successfully returned by ValueInvesting.io. The coverage percentage
is measured against the entire ETF, not just the supported-country subset. It is a
partial constituent valuation indicator, never a certified fair value for the ETF.

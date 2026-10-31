# ETF constituents

Place dated holdings files here. Required CSV columns:

- ticker: constituent equity ticker accepted by the selected data provider
- weight: portfolio weight as a fraction (0.025) or percentage (2.5); the loader normalizes
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

Weights should sum to approximately 1.0 (or 100 if you explicitly normalize them first).
Use issuer holdings files or a licensed data provider. Include an as_of date and source
in a companion metadata file. Do not assume current holdings represent historical holdings.

## Interpretation

The weighted DCF upside is calculated only on constituents that are both in the US/Canada
subscription scope and successfully returned by ValueInvesting.io. The coverage percentage
is measured against the entire ETF, not just the supported-country subset. It is a
partial constituent valuation indicator, never a certified fair value for the ETF.

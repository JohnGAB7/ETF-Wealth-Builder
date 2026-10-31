"""Issuer holdings conversion: equity-only, whole-fund weights, explicit US/CA gate."""
import pandas as pd
import pytest

from src.data import analyst_data, holdings_import as hi
from src.data.holdings import load_holdings_with_meta

ISHARES = '''Fund Holdings as of,"29/Oct/2026"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,Exchange,Market Currency
"AAPL","APPLE","Information Technology","Equity","1,000.00","5.00","1,000.00","10.00","348.91","United States","NASDAQ","USD"
"RY","ROYAL BANK OF CANADA","Financials","Equity","500.00","2.00","500.00","5.00","206.20","Canada","Toronto Stock Exchange","CAD"
"ASML","ASML HOLDING NV","Information Technology","Equity","400.00","1.50","400.00","1.00","900.00","Netherlands","Euronext Amsterdam","EUR"
"NBIS","NEBIUS GROUP NV","Information Technology","Equity","50.00","0.20","50.00","1.00","90.00","Netherlands","NASDAQ","USD"
"TJX","TJX","Consumer Discretionary","Equity","50.00","0.30","50.00","1.00","141.39","United States","New York Stock Exchange Inc.","USD"
"XYZ","UNLISTED CO","Industrials","Equity","1.00","0.01","1.00","1.00","1.00","United States","NO MARKET (E.G. UNLISTED)","USD"
"USD","USD CASH","Cash and/or Derivatives","Cash","10.00","0.40","10.00","10.00","1.00","United States","-","USD"
"ES","S&P500 EMINI DEC 26","Cash and/or Derivatives","Futures","0.00","-0.10","1.00","1.00","1.00","United States","-","USD"

"The content contained herein is owned or licensed by BlackRock"
'''


@pytest.fixture
def ishares_file(tmp_path):
    path = tmp_path / "SWDA_holdings.csv"
    path.write_text(ISHARES, encoding="utf-8")
    return path


def test_market_label_requires_country_and_venue():
    assert hi.market_label("United States", "NASDAQ") == "US"
    assert hi.market_label("Canada", "Toronto Stock Exchange") == "CA"
    assert hi.market_label("Netherlands", "NASDAQ") == "Netherlands"   # ADR-style listing
    assert hi.market_label("United States", "NO MARKET (E.G. UNLISTED)") == "United States"
    assert hi.market_label("", "NASDAQ") == ""


def test_read_ishares_keeps_equity_only_without_rescaling(ishares_file):
    frame, as_of = hi.read_ishares(ishares_file)
    assert as_of == "2026-10-29"
    assert "USD" not in set(frame["ticker"]) and "ES" not in set(frame["ticker"])
    assert frame["weight"].sum() == pytest.approx(9.01)   # cash/futures not redistributed
    markets = dict(zip(frame["ticker"], frame["market"]))
    assert markets == {"AAPL": "US", "RY": "CA", "ASML": "Netherlands",
                       "NBIS": "Netherlands", "TJX": "US", "XYZ": "United States"}


def test_written_file_loads_as_whole_fund_fraction(ishares_file, tmp_path, monkeypatch):
    frame, as_of = hi.read_ishares(ishares_file)
    out = tmp_path / "out"
    path = hi.write_constituents(frame, "iwda", as_of, "iShares holdings download", out)
    meta_text = (out / "iwda_constituents.meta.yaml").read_text(encoding="utf-8")
    assert "as_of: '2026-10-29'" in meta_text and "weight_unit: percent" in meta_text
    monkeypatch.setattr("src.data.holdings.ROOT", tmp_path)
    rows, meta = load_holdings_with_meta(str(path.relative_to(tmp_path)))
    assert meta["weight_unit"] == "percent" and meta["as_of"] == "2026-10-29"
    assert meta["file_weight"] == pytest.approx(0.0901)
    assert "weight_unit_inferred" not in meta["warnings"]
    assert rows[0]["ticker"] == "AAPL"   # sorted by weight


def test_ssga_rows_get_tickers_only_on_country_price_and_name_match(ishares_file):
    ref, _ = hi.read_ishares(ishares_file)
    ssga = pd.DataFrame([
        # same price, close name
        {"ticker": "US0378331005", "weight": 5.6, "market": "US", "name": "Apple Inc.",
         "isin": "US0378331005", "location": "United States", "exchange": "",
         "ticker_source": "isin", "_price": 348.91},
        # Canadian price in CAD: matched after the per-country factor
        {"ticker": "CA7800871021", "weight": 0.3, "market": "CA", "name": "Royal Bank of Canada",
         "isin": "CA7800871021", "location": "Canada", "exchange": "",
         "ticker_source": "isin", "_price": 288.21},
        # sole price candidate, weak but acceptable name similarity
        {"ticker": "US8725401090", "weight": 0.17, "market": "US", "name": "TJX Companies Inc",
         "isin": "US8725401090", "location": "United States", "exchange": "",
         "ticker_source": "isin", "_price": 141.39},
        # same price as Apple but a different company: must stay unmatched
        {"ticker": "US0000000001", "weight": 0.1, "market": "US", "name": "Zebra Widgets Corp",
         "isin": "US0000000001", "location": "United States", "exchange": "",
         "ticker_source": "isin", "_price": 348.91},
    ])
    out = hi.attach_tickers(ssga, [ref]).set_index("isin")
    assert out.loc["US0378331005", "ticker"] == "AAPL"
    assert out.loc["CA7800871021", "ticker"] == "RY"
    assert out.loc["US8725401090", "ticker"] == "TJX"
    assert out.loc["US0000000001", "ticker_source"] == "isin"
    summary = hi.summary(out.reset_index())
    assert summary["us_ca_weight_pct"] == pytest.approx(6.17)
    assert summary["us_ca_with_ticker_pct"] == pytest.approx(6.07)


def test_analyst_queries_only_largest_lines(monkeypatch):
    asked = []
    monkeypatch.setattr(analyst_data, "get_company_recommendations",
                        lambda t: asked.append(t) or [{"buy": 1, "hold": 0, "sell": 0}])
    holdings = [{"ticker": f"T{i}", "weight": i / 1000} for i in range(40)]
    result = analyst_data.aggregate_recommendations(holdings, max_constituents=5)
    assert asked == ["T39", "T38", "T37", "T36", "T35"]
    assert result["analyst_constituents_queried"] == 5
    assert result["analyst_coverage_weight"] == pytest.approx(sum(range(35, 40)) / 1000)


def test_read_vanguard(tmp_path):
    rows = [["This file was downloaded on 31 Oct 2026"], [None], ["Holdings details"],
            ["Vanguard FTSE All-World UCITS ETF (USD) Accumulating"], ["As at 30 Sept 2026"], [None],
            ["Ticker", "Holding name", "% of market value", "Sector", "Region", "Market value", "Shares"],
            ["NVDA", "NVIDIA Corp", "5.0056%", "Technology", "US", "US$1", "1"],
            ["BRK/B", "Berkshire Hathaway Inc", "0.6%", "Financials", "US", "US$1", "1"],
            ["BP/", "BP PLC", "0.1%", "Energy", "GB", "US$1", "1"],
            [None, "National Bank of Canada", "0.052%", "Financials", "CA", "US$1", "1"],
            ["NDA", "Nordea Bank Abp", "0.00%", "Financials", "SE", "US$0", "0"],
            [None], ["Total allocation percentages shown may not equal 100%"]]
    path = tmp_path / "vg.xlsx"
    pd.DataFrame(rows).to_excel(path, header=False, index=False)
    frame, as_of = hi.read_vanguard(path)
    assert as_of == "2026-09-30"
    assert list(frame["ticker"]) == ["NVDA", "BRK/B", "BP"]
    assert list(frame["market"]) == ["US", "US", "GB"]
    assert frame["weight"].sum() == pytest.approx(5.7056)


def test_valuations_requested_once_per_ticker_per_run(monkeypatch):
    from src.data import valueinvesting as vi
    calls = []

    class _Resp:
        def __init__(self, tickers):
            self._t = tickers

        def raise_for_status(self):
            pass

        def json(self):
            return {t: {"upside_dcf_ebitda_10": 0.1} for t in self._t if t != "ZZZ"}

    class _Session:
        def get(self, url, params, timeout):
            batch = params["tickers"].split(",")
            calls.append(batch)
            return _Resp(batch)

    monkeypatch.setenv("VALUEINVESTING_API_KEY", "test-key")
    monkeypatch.setattr(vi.requests, "Session", _Session)
    first = vi.get_valuations(["AAPL", "MSFT", "ZZZ", "AAPL"])
    second = vi.get_valuations(["MSFT", "ZZZ", "NVDA"])
    assert calls == [["AAPL", "MSFT", "ZZZ"], ["NVDA"]]
    assert set(first) == {"AAPL", "MSFT"} and set(second) == {"MSFT", "NVDA"}

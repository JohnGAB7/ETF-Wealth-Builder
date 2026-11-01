"""Convert issuer holdings downloads into the project's constituents format.

Supported inputs:
- iShares "Fund Holdings" CSV (line 1 "Fund Holdings as of", header on the
  line starting with "Ticker,Name,...", comma thousand separators).
- SSGA (SPDR) daily holdings XLSX ("Holdings As Of:" cell, header row starting
  with "ISIN", weights in "Percent of Fund").
- Vanguard "Holdings details" XLSX ("As at 30 Sept 2026" cell, header row starting
  with "Ticker", weights in "% of market value", country code in "Region").

Output columns: ticker, weight (percent of the WHOLE fund, never rescaled),
market, name, isin, location, exchange, ticker_source.

Rules (see data/constituents/README.md):
- only equity rows are kept; cash, FX, futures and money-market lines are dropped
  and simply reduce the total weight of the file;
- `market` is "US" / "CA" only when BOTH the issuer's country (Location) and the
  listing venue are US / Canadian. Every other row keeps its country label, so it
  is never sent to ValueInvesting.io. Nothing is inferred from ticker syntax;
- SSGA files carry no ticker. A ticker is taken from an iShares file of the same
  date when the country, the local price and the name all match
  (`ticker_source = ishares_match`); otherwise the ISIN is used as identifier
  (`ticker_source = isin`) and no provider will value that line.

Usage:
    python -m src.data.holdings_import ishares FILE --id iwda
    python -m src.data.holdings_import ssga FILE --id spyl --ticker-ref CSPX.csv [--ticker-ref ...]
    python -m src.data.holdings_import vanguard FILE --id vwce
"""
import argparse
import csv
import difflib
import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from src.config import ROOT

OUT_COLUMNS = ["ticker", "weight", "market", "name", "isin", "location",
               "exchange", "ticker_source"]

US_VENUES = ("new york stock exchange", "nyse", "nasdaq", "cboe", "bats")
CA_VENUES = ("toronto stock exchange", "tsx", "neo exchange", "cboe canada")
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

_NAME_NOISE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|companies|ltd|limited|plc|ag|sa|nv|se|"
    r"class [a-z]|cl [a-z]|holdings?|group|the|reit|trust)\b")


def market_label(location: str, exchange: str = "") -> str:
    """US/CA only when country and venue agree; otherwise the country label."""
    location = (location or "").strip()
    venue = (exchange or "").strip().lower()
    if location == "United States" and any(v in venue for v in US_VENUES):
        return "US"
    if location == "Canada" and any(v in venue for v in CA_VENUES):
        return "CA"
    return location or ""


def _number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "nan"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(text: str):
    text = re.sub(r"\bSept\b", "Sep", str(text))
    for fmt in ("%d/%b/%Y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_name(name: str) -> str:
    text = re.sub(r"['’.]", "", str(name or "").lower())  # O'Reilly, W.W. Grainger
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = _NAME_NOISE.sub(" ", text)
    return " ".join(text.split())


# --------------------------------------------------------------------- iShares

def read_ishares(path: Path) -> tuple[pd.DataFrame, str | None]:
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    as_of = None
    first = next(csv.reader([lines[0]])) if lines else []
    if len(first) >= 2 and first[0].lower().startswith("fund holdings as of"):
        as_of = _parse_date(first[1])
    start = next(i for i, line in enumerate(lines) if line.startswith("Ticker,"))
    body = []
    for line in lines[start:]:
        if not line.strip():
            break  # iShares appends a disclaimer after a blank line
        body.append(line)
    raw = pd.read_csv(io.StringIO("\n".join(body)), dtype=str, keep_default_na=False)
    rows = []
    for _, r in raw.iterrows():
        if r.get("Asset Class", "").strip() != "Equity":
            continue
        weight = _number(r.get("Weight (%)"))
        ticker = r.get("Ticker", "").strip()
        if weight is None or weight <= 0 or ticker in ("", "-"):
            continue
        rows.append({
            "ticker": ticker, "weight": weight,
            "market": market_label(r.get("Location"), r.get("Exchange")),
            "name": r.get("Name", "").strip(), "isin": "",
            "location": r.get("Location", "").strip(),
            "exchange": r.get("Exchange", "").strip(),
            "ticker_source": "issuer",
            "_price": _number(r.get("Price")),
        })
    return pd.DataFrame(rows), as_of


# ------------------------------------------------------------------------ SSGA

def read_ssga(path: Path) -> tuple[pd.DataFrame, str | None]:
    raw = pd.read_excel(path, header=None, dtype=object)
    as_of = None
    header_row = None
    for i, value in raw[0].items():
        label = str(value).strip()
        if label.lower().startswith("holdings as of"):
            cell = raw.iat[i, 1]
            as_of = (cell.date().isoformat() if hasattr(cell, "date")
                     else _parse_date(str(cell)))
        if label == "ISIN":
            header_row = i
            break
    if header_row is None:
        raise ValueError("SSGA file: header row starting with 'ISIN' not found")
    frame = raw.iloc[header_row + 1:].copy()
    frame.columns = [str(c).strip() for c in raw.iloc[header_row]]
    rows = []
    for _, r in frame.iterrows():
        isin = str(r.get("ISIN") or "").strip()
        if not ISIN_RE.match(isin):
            continue  # cash, currency, futures and footer lines carry no ISIN
        weight = _number(r.get("Percent of Fund"))
        if weight is None or weight <= 0:
            continue
        location = str(r.get("Trade Country Name") or "").strip()
        rows.append({
            "ticker": isin, "weight": weight,
            # SSGA gives no listing venue: the trade country stands for it.
            "market": market_label(location, _ssga_venue(location)),
            "name": str(r.get("Security Name") or "").strip(), "isin": isin,
            "location": location, "exchange": "",
            "ticker_source": "isin",
            "_price": _number(r.get("Local Price")),
        })
    return pd.DataFrame(rows), as_of


def _ssga_venue(location: str) -> str:
    return {"United States": "nyse/nasdaq", "Canada": "toronto stock exchange"}.get(location, "")


def _price_ratios(ssga: pd.DataFrame, ref: pd.DataFrame) -> dict:
    """Median SSGA/iShares price ratio per country, from rows whose names match exactly.

    SSGA quotes the local price (CAD, JPY...) while iShares quotes in the fund
    currency, so prices only agree after this per-country conversion factor.
    """
    by_name = {(r["location"], normalize_name(r["name"])): r["_price"]
               for _, r in ref.iterrows()}
    ratios: dict = {}
    for _, row in ssga.iterrows():
        ref_price = by_name.get((row["location"], normalize_name(row["name"])))
        if ref_price and row["_price"]:
            ratios.setdefault(row["location"], []).append(row["_price"] / ref_price)
    return {loc: float(pd.Series(vals).median()) for loc, vals in ratios.items()}


def attach_tickers(ssga: pd.DataFrame, references: list[pd.DataFrame],
                   price_tolerance: float = 0.005, min_name_ratio: float = 0.6,
                   sole_candidate_ratio: float = 0.3) -> pd.DataFrame:
    """Copy iShares tickers onto SSGA rows when country, price and name agree.

    A candidate must be in the same country and have the same price (after the
    per-country currency factor, within `price_tolerance`). Among candidates, the
    closest name wins if similar enough; a sole price candidate needs only a
    weaker name similarity (e.g. "TJX Companies Inc" vs "TJX").
    """
    if ssga.empty or not references:
        return ssga
    ref = pd.concat(references, ignore_index=True)
    ref = ref[ref["_price"].notna() & (ref["_price"] > 0)].drop_duplicates(
        subset=["ticker", "location", "exchange"])
    fx = _price_ratios(ssga, ref)
    by_location = {loc: grp for loc, grp in ref.groupby("location")}
    out = ssga.copy()
    for i, row in out.iterrows():
        price, factor = row["_price"], fx.get(row["location"])
        group = by_location.get(row["location"])
        if not price or factor is None or group is None:
            continue
        rel = (price / (group["_price"] * factor) - 1).abs()
        candidates = group[rel <= price_tolerance]
        if candidates.empty:
            continue
        target = normalize_name(row["name"])
        scored = [(difflib.SequenceMatcher(None, target, normalize_name(c["name"])).ratio(), c)
                  for _, c in candidates.iterrows()]
        best_ratio, best = max(scored, key=lambda item: item[0])
        needed = sole_candidate_ratio if len(scored) == 1 else min_name_ratio
        if best_ratio >= needed:
            out.at[i, "ticker"] = best["ticker"]
            out.at[i, "exchange"] = best["exchange"]
            out.at[i, "market"] = market_label(row["location"], best["exchange"])
            out.at[i, "ticker_source"] = "ishares_match"
    return out


# -------------------------------------------------------------------- Vanguard

def read_vanguard(path: Path) -> tuple[pd.DataFrame, str | None]:
    """Vanguard lists equities only, with a country code and no listing venue.

    `market` is therefore the country code: "US" / "CA" rows are US / Canadian
    companies, whose Vanguard ticker is their home (US / Canadian) listing.
    Rows without a ticker are skipped (they cannot be sent to any provider) and
    only lower the file total; tickers are kept as published (e.g. "BRK/B"),
    except a trailing "/" (e.g. "BP/") which is dropped.
    """
    raw = pd.read_excel(path, header=None, dtype=object)
    as_of, header_row = None, None
    for i, value in raw[0].items():
        label = str(value).strip()
        if label.lower().startswith("as at "):
            as_of = _parse_date(label[6:])
        if label == "Ticker":
            header_row = i
            break
    if header_row is None:
        raise ValueError("Vanguard file: header row starting with 'Ticker' not found")
    frame = raw.iloc[header_row + 1:].copy()
    frame.columns = [str(c).strip() for c in raw.iloc[header_row]]
    rows = []
    for _, r in frame.iterrows():
        ticker = str(r.get("Ticker") or "").strip()
        if ticker.lower() == "nan":
            ticker = ""
        ticker = ticker.rstrip("/")
        weight = _number(str(r.get("% of market value") or "").rstrip("%"))
        if not ticker or weight is None or weight <= 0:
            continue
        region = str(r.get("Region") or "").strip().upper()
        rows.append({
            "ticker": ticker, "weight": weight,
            "market": region,
            "name": str(r.get("Holding name") or "").strip(), "isin": "",
            "location": region, "exchange": "", "ticker_source": "issuer",
            "_price": None,
        })
    return pd.DataFrame(rows), as_of


# ---------------------------------------------------------------------- output

def summary(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"rows": 0, "file_weight_pct": 0.0, "us_ca_weight_pct": 0.0}
    us_ca = frame[frame["market"].isin(["US", "CA"])]
    valued = us_ca[us_ca["ticker_source"] != "isin"]
    return {
        "rows": int(len(frame)),
        "file_weight_pct": round(float(frame["weight"].sum()), 2),
        "us_ca_weight_pct": round(float(us_ca["weight"].sum()), 2),
        "us_ca_with_ticker_pct": round(float(valued["weight"].sum()), 2),
    }


def write_constituents(frame: pd.DataFrame, etf_id: str, as_of: str | None,
                       source: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or ROOT / "data" / "constituents")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{etf_id}_constituents.csv"
    frame = frame.sort_values("weight", ascending=False)
    frame[OUT_COLUMNS].to_csv(csv_path, index=False)
    meta = {"as_of": as_of, "source": source, "weight_unit": "percent",
            "generated_by": "src.data.holdings_import", **summary(frame)}
    meta_path = out_dir / f"{etf_id}_constituents.meta.yaml"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    return csv_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("format", choices=["ishares", "ssga", "vanguard"])
    parser.add_argument("file")
    parser.add_argument("--id", required=True, help="ETF id from config/etf_universe.yaml")
    parser.add_argument("--ticker-ref", action="append", default=[],
                        help="iShares CSV of the same date used to find SSGA tickers")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    if args.format == "ishares":
        frame, as_of = read_ishares(Path(args.file))
        source = "iShares holdings download"
    elif args.format == "vanguard":
        frame, as_of = read_vanguard(Path(args.file))
        source = "Vanguard holdings download"
    else:
        frame, as_of = read_ssga(Path(args.file))
        refs = [read_ishares(Path(p))[0] for p in args.ticker_ref]
        frame = attach_tickers(frame, refs)
        source = "SSGA (SPDR) holdings download"
    path = write_constituents(frame, args.id, as_of, source, args.out)
    print(path, as_of, summary(frame))


if __name__ == "__main__":
    main()

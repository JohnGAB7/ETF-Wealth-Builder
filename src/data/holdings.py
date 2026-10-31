"""Load dated ETF constituent files without inflating their coverage.

Weights are kept as a fraction of the *whole ETF*. A partial file (for example
the top 200 lines, about 45 % of the fund) therefore keeps a total of about 0.45:
it is never rescaled to 100 %, so every coverage figure computed from it stays
expressed against the total weight of the ETF.

Optional companion metadata, next to the CSV, named `<file stem>.meta.yaml`:

    as_of: 2026-09-30        # holdings date published by the issuer
    source: iShares website  # where the file comes from
    weight_unit: percent     # "fraction" (0.045) or "percent" (4.5)
"""
import logging
from pathlib import Path

import pandas as pd
import yaml

from src.config import ROOT

log = logging.getLogger(__name__)

# A file whose weights add up to more than this is inconsistent (duplicates,
# mixed units); it is reported, and coverage is then measured against its sum.
SUM_TOLERANCE = 1.02


def empty_meta(path: str = "") -> dict:
    return {"path": path, "file_weight": 0.0, "as_of": None, "source": None,
            "weight_unit": None, "rows": 0, "warnings": []}


def _read_meta(csv_path: Path) -> dict:
    meta_path = csv_path.with_name(csv_path.stem + ".meta.yaml")
    if not meta_path.exists():
        return {}
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("Holdings metadata %s unreadable: %s", meta_path.name, type(exc).__name__)
        return {}


def load_holdings_with_meta(path: str) -> tuple[list[dict], dict]:
    """Return (rows, meta). Rows carry `weight` as a fraction of the whole ETF."""
    meta = empty_meta(path)
    if not path:
        return [], meta
    file_path = ROOT / path
    if not file_path.exists():
        meta["warnings"].append("missing_file")
        return [], meta
    try:
        frame = pd.read_csv(file_path)
    except Exception as exc:
        log.warning("Could not read holdings %s: %s", path, type(exc).__name__)
        meta["warnings"].append("unreadable_file")
        return [], meta
    if not {"ticker", "weight"}.issubset(frame.columns):
        log.warning("Holdings file %s must contain ticker,weight", path)
        meta["warnings"].append("missing_columns")
        return [], meta

    extra = _read_meta(file_path)
    meta["as_of"] = str(extra["as_of"]) if extra.get("as_of") else None
    meta["source"] = str(extra["source"]) if extra.get("source") else None

    frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
    frame = frame.dropna(subset=["ticker", "weight"])
    frame = frame[frame["weight"] > 0]
    if frame.empty:
        meta["warnings"].append("no_valid_rows")
        return [], meta

    unit = str(extra.get("weight_unit") or "").strip().lower()
    if unit not in ("fraction", "percent"):
        # Without metadata: a single weight above 1 can only be a percentage.
        unit = "percent" if frame["weight"].max() > 1.0 else "fraction"
        meta["warnings"].append("weight_unit_inferred")
    if unit == "percent":
        frame["weight"] = frame["weight"] / 100.0
    meta["weight_unit"] = unit

    total = float(frame["weight"].sum())
    if total > SUM_TOLERANCE:
        log.warning("Holdings %s: weights sum to %.3f (> 1); check units and duplicates",
                    path, total)
        meta["warnings"].append("weights_exceed_100pct")
    meta["file_weight"] = total
    meta["rows"] = int(len(frame))
    return frame.to_dict("records"), meta


def etf_total_weight(meta: dict) -> float:
    """Denominator for every coverage figure: the whole ETF (1.0), or the file sum
    if an inconsistent file adds up to more than 100 %."""
    return max(1.0, float(meta.get("file_weight") or 0.0))

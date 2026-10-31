import json
import math

import pandas as pd
import pytest

import src.data.holdings as holdings_mod
from src.data.holdings import etf_total_weight, load_holdings_with_meta
from src.data.macro_data import year_over_year_change
from src.data.valueinvesting import weighted_constituent_upside
from src.notifications.email_alert import compose_digest
from src.notifications.view_model import build_macro, macro_is_old
from src.reporting.report import write_report


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(holdings_mod, "ROOT", tmp_path)
    return tmp_path


def test_partial_holdings_file_is_not_rescaled_to_100pct(root):
    (root / "top.csv").write_text("ticker,weight,market\nAAA,0.30,US\nBBB,0.15,NL\n")
    rows, meta = load_holdings_with_meta("top.csv")
    assert sum(r["weight"] for r in rows) == pytest.approx(0.45)
    assert meta["file_weight"] == pytest.approx(0.45)
    payload = {"AAA": {"valuation": {"upside_dcf_ebitda_10": 0.10}}}
    result = weighted_constituent_upside(payload, rows, etf_total_weight=etf_total_weight(meta))
    # 30 % of the whole ETF is valued, not 30/45 = 67 %.
    assert result["coverage_weight"] == pytest.approx(0.30)
    assert result["holdings_file_weight"] == pytest.approx(0.45)
    assert result["supported_market_weight"] == pytest.approx(0.30)


def test_percent_weights_detected_or_declared(root):
    (root / "pct.csv").write_text("ticker,weight,market\nAAA,4.5,US\nBBB,0.5,CA\n")
    rows, meta = load_holdings_with_meta("pct.csv")
    assert meta["weight_unit"] == "percent" and "weight_unit_inferred" in meta["warnings"]
    assert meta["file_weight"] == pytest.approx(0.05)

    # All weights below 1 % but declared as percent in the metadata file.
    (root / "small.csv").write_text("ticker,weight,market\nAAA,0.9,US\nBBB,0.5,CA\n")
    (root / "small.meta.yaml").write_text(
        "as_of: 2026-09-30\nsource: issuer\nweight_unit: percent\n")
    rows, meta = load_holdings_with_meta("small.csv")
    assert meta["file_weight"] == pytest.approx(0.014)
    assert meta["as_of"] == "2026-09-30" and meta["source"] == "issuer"
    assert "weight_unit_inferred" not in meta["warnings"]


def test_overweight_file_is_flagged_and_coverage_capped(root):
    (root / "dup.csv").write_text("ticker,weight,market\nAAA,0.8,US\nAAA,0.4,US\n")
    rows, meta = load_holdings_with_meta("dup.csv")
    assert "weights_exceed_100pct" in meta["warnings"]
    payload = {"AAA": {"valuation": {"upside_dcf_ebitda_10": 0.1}}}
    result = weighted_constituent_upside(payload, rows, etf_total_weight=etf_total_weight(meta))
    assert result["coverage_weight"] <= 1.0


def test_missing_holdings_file_is_reported(root):
    rows, meta = load_holdings_with_meta("absent.csv")
    assert rows == [] and "missing_file" in meta["warnings"]


def test_implausible_upside_is_excluded_not_rescaled():
    holdings = [{"ticker": "AAA", "weight": 0.5, "market": "US"},
                {"ticker": "BBB", "weight": 0.5, "market": "US"}]
    payload = {"AAA": {"valuation": {"upside_dcf_ebitda_10": 25.0}},   # looks like percent
               "BBB": {"valuation": {"upside_dcf_ebitda_10": 0.10}}}
    result = weighted_constituent_upside(payload, holdings)
    assert result["implausible_upside_count"] == 1
    assert result["weighted_upside"] == pytest.approx(0.10)
    assert result["coverage_weight"] == pytest.approx(0.5)


def test_cpi_year_over_year_uses_same_month_only():
    idx = pd.date_range("2025-01-01", periods=21, freq="MS")
    series = pd.Series([100 + i for i in range(21)], index=idx, dtype=float)
    value, period = year_over_year_change(series)
    assert period == "2026-09-01"
    assert value == pytest.approx((120 / 108 - 1) * 100)
    # Missing the comparison month: no substitution.
    gap = series.drop(pd.Timestamp("2025-09-01"))
    assert year_over_year_change(gap) == (None, None)


def test_old_macro_observations_are_flagged_with_their_dates():
    assert macro_is_old("2026-03", "M", "2026-10-31")
    assert not macro_is_old("2026-09", "M", "2026-10-31")
    assert macro_is_old("2025-Q4", "Q", "2026-10-31")
    assert not macro_is_old("2026-Q2", "Q", "2026-10-31")
    macro = build_macro({"eurostat_hicp_yoy_be": 2.4, "eurostat_hicp_yoy_be_date": "2026-03"},
                        "2026-10-31")
    assert macro["old"] == ["Inflation HICP (sur un an) (Belgique)"]
    assert "mars 2026 · observation ancienne" in macro["groups"][0]["rows"][0]["period"]


def test_stale_price_block_is_explained():
    item = {"id": "vwce", "name": "VWCE", "symbol": "VWCE.DE", "signal": "INSUFFICIENT_EVIDENCE",
            "score": 80, "prob_positive": 0.7, "data_coverage": 0.8, "price": 100.0,
            "as_of": "2026-10-20", "price_age_days": 11, "price_stale": True,
            "max_price_age_days": 5}
    _, text, _ = compose_digest([item], "2026-10-31")
    assert "Dernier cours daté de 11 jours (maximum 5)" in text


def test_holdings_metadata_shown_in_email():
    item = {"id": "vwce", "name": "VWCE", "symbol": "VWCE.DE", "signal": "REGULAR_DCA",
            "score": 40, "holdings_file_weight": 0.45, "holdings_as_of": "2026-09-30",
            "holdings_source": "Vanguard"}
    _, text, _ = compose_digest([item], "2026-10-31")
    assert "Fichier de constituants : 45 % du poids de l’ETF, au 30/09/2026 (source : Vanguard)." in text
    _, text, _ = compose_digest([{**item, "holdings_file_weight": 0.0}], "2026-10-31")
    assert "Aucun fichier de constituants exploitable" in text


def test_report_json_has_no_nan(tmp_path):
    path = write_report({"a": float("nan"), "b": [float("inf"), 1.0], "c": {"d": math.nan}},
                        output_dir=str(tmp_path))
    data = json.loads(path.read_text())
    assert data == {"a": None, "b": [None, 1.0], "c": {"d": None}}

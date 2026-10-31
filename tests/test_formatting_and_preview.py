from src.notifications.formatting import (
    fr_date, fr_number, fr_percent, fr_period, fr_score,
)
from src.notifications.preview import write_previews

NBSP = " "


def test_french_number_formats():
    assert fr_number(1234.5) == f"1{NBSP}234,50"
    assert fr_percent(0.64, 0) == f"64{NBSP}%"
    assert fr_percent(0.035, 1, signed=True) == f"+3,5{NBSP}%"
    assert fr_score(62.5) == "63/100"  # half-up, not banker's rounding


def test_missing_values_stay_missing():
    assert fr_number(None) == "—"
    assert fr_number(float("nan")) == "—"
    assert fr_percent(None) == "—"


def test_periods_keep_their_meaning():
    assert fr_period("2026-10-30", "D") == "30/10/2026"
    assert fr_period("2026-09", "M") == "sept. 2026"
    assert fr_period("2026-09-01", "M") == "sept. 2026"
    assert fr_period("2026-Q2", "Q") == "T2 2026"
    assert fr_date("2026-10-30 00:00:00") == "30/10/2026"


def test_preview_generation_writes_all_scenarios(tmp_path):
    paths = write_previews(tmp_path)
    names = {p.name for p in paths}
    assert "digest_opportunity.html" in names and "alert_opportunity.txt" in names
    assert len(paths) == 10
    for path in paths:
        assert path.stat().st_size > 500
    assert not list(tmp_path.glob("*.eml"))

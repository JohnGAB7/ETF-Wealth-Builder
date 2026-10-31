from unittest.mock import patch

from src.notifications.email_alert import send_digest


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_daily_digest_includes_european_macro_values(mock_send_email):
    macro = {
        "ecb_deposit_facility_rate": 2.0,
        "ecb_deposit_facility_rate_date": "2026-10-30",
        "eurostat_hicp_yoy_be": 2.4,
        "eurostat_hicp_yoy_be_date": "2026-09",
        "eurostat_gdp_qoq_ea21": 0.2,
        "eurostat_gdp_qoq_ea21_date": "2026-Q2",
    }
    assert send_digest([], "2026-10-31", macro_snapshot=macro) is True
    subject, body = mock_send_email.call_args.args
    assert "Rapport quotidien" in subject
    assert "Taux de dépôt BCE: 2.00%" in body
    assert "Inflation HICP Belgique (sur un an): 2.40%" in body
    assert "PIB zone euro (EA21, variation trimestrielle): 0.20%" in body
    assert "période: 2026-Q2" in body


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_daily_digest_marks_missing_macro_fields_as_unavailable(mock_send_email):
    assert send_digest([], "2026-10-31", macro_snapshot={}) is True
    body = mock_send_email.call_args.args[1]
    assert "Taux de dépôt BCE: indisponible" in body
    assert "Inflation HICP Belgique (sur un an): indisponible" in body

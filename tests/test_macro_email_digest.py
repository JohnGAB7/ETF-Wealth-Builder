from unittest.mock import patch

from src.notifications.email_alert import send_digest, send_signal_alert


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_daily_digest_has_clear_summary_html_and_macro_values(mock_send_email):
    macro = {
        "ecb_deposit_facility_rate": 2.0,
        "ecb_deposit_facility_rate_date": "2026-10-30",
        "eurostat_hicp_yoy_be": 2.4,
        "eurostat_hicp_yoy_be_date": "2026-09",
        "eurostat_gdp_qoq_ea21": 0.2,
        "eurostat_gdp_qoq_ea21_date": "2026-Q2",
    }
    results = [{
        "id": "vwce",
        "name": "Vanguard FTSE All-World UCITS ETF",
        "symbol": "VWCE.DE",
        "signal": "WATCH",
        "score": 62.5,
        "price": 138.25,
        "prob_positive": 0.64,
        "expected_return": 0.035,
        "drawdown": -0.08,
        "data_coverage": 0.82,
        "valuation_coverage_weight": 0.34,
    }]

    assert send_digest(results, "2026-10-31", macro_snapshot=macro) is True
    subject, body = mock_send_email.call_args.args
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "Point quotidien" in subject
    assert "SYNTHÈSE" in body
    assert "À surveiller : 1" in body
    assert "Taux de dépôt BCE: 2.00%" in body
    assert "Inflation HICP: 2.40%" in body
    assert "PIB, variation trimestrielle: 0.20%" in body
    assert "période: 2026-Q2" in body
    assert "Couverture fondamentale US/Canada" in body
    assert "<!doctype html>" in html.lower()
    assert "Analyse des ETF" in html
    assert "Contexte macroéconomique" in html
    assert "Vanguard FTSE All-World UCITS ETF" in html


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_missing_macro_fields_are_omitted_instead_of_filling_the_email(mock_send_email):
    assert send_digest([], "2026-10-31", macro_snapshot={}) is True
    body = mock_send_email.call_args.args[1]
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "Aucune observation macroéconomique disponible" in body
    assert "indisponible" not in body
    assert "Taux de dépôt BCE" not in body
    assert "Aucune observation macroéconomique disponible" in html


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_immediate_signal_alert_uses_the_same_html_design(mock_send_email):
    result = {
        "id": "vwce",
        "name": "Vanguard FTSE All-World UCITS ETF",
        "symbol": "VWCE.DE",
        "score": 82,
        "prob_positive": 0.71,
        "expected_return": 0.045,
        "price": 140.12,
        "drawdown": -0.06,
        "data_coverage": 0.88,
        "valuation_coverage_weight": 0.32,
        "as_of": "2026-10-30",
    }

    assert send_signal_alert(result, 63) is True
    subject, body = mock_send_email.call_args.args
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "Signal à examiner" in subject
    assert "63 jours" in body
    assert "Ce signal est une invitation" in body
    assert "OPPORTUNITÉ À EXAMINER" in html
    assert "Vanguard FTSE All-World UCITS ETF" not in html or "Signal à examiner" in html

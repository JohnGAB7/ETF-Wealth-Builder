from unittest.mock import patch

from src.notifications.email_alert import (
    compose_digest, format_macro_digest, send_digest, send_signal_alert,
)
from src.notifications.preview import MACRO_FULL, scenarios

NBSP = " "


def _watch_item(**overrides):
    item = {
        "id": "vwce", "name": "Vanguard FTSE All-World UCITS ETF", "isin": "IE00BK5BQT80",
        "symbol": "VWCE.DE", "currency": "EUR", "signal": "WATCH", "score": 62.5,
        "price": 138.25, "as_of": "2026-10-30", "prob_positive": 0.64,
        "expected_return": 0.035, "base_rate_positive": 0.68, "drawdown": -0.08,
        "data_coverage": 0.82, "valuation_coverage_weight": 0.34, "horizon_days": 63,
        "validation": {"brier": 0.25, "brier_reference": 0.24, "auc": 0.5},
    }
    item.update(overrides)
    return item


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
    assert send_digest([_watch_item()], "2026-10-31", macro_snapshot=macro) is True
    subject, body = mock_send_email.call_args.args
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "31/10/2026" in subject and "1 à surveiller" in subject
    assert "SYNTHÈSE" in body
    assert "À surveiller : 1" in body
    assert f"Taux de dépôt BCE : 2,00{NBSP}%" in body
    assert f"Inflation HICP (sur un an) : 2,4{NBSP}%" in body
    assert "période : T2 2026" in body
    assert "période : sept. 2026" in body
    assert "du poids total de l’ETF" in body
    assert "<!doctype html>" in html.lower()
    assert "Fiches ETF" in html
    assert "Contexte macroéconomique" in html
    assert "Vanguard FTSE All-World UCITS ETF" in html


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_missing_macro_fields_are_omitted_instead_of_filling_the_email(mock_send_email):
    assert send_digest([], "2026-10-31", macro_snapshot={}) is True
    body = mock_send_email.call_args.args[1]
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "Aucune observation macroéconomique disponible" in body
    assert "Taux de dépôt BCE" not in body
    assert "Aucune observation macroéconomique disponible" in html


def test_partially_missing_macro_series_are_listed_not_imputed():
    lines = format_macro_digest({"ecb_deposit_facility_rate": 2.0,
                                 "ecb_deposit_facility_rate_date": "2026-10-30"})
    text = "\n".join(lines)
    assert "1/14 séries disponibles." in text
    assert "Indisponibles ce jour :" in text
    assert "Taux directeur Fed Funds (États-Unis)" in text
    # No placeholder number is invented for a missing series.
    assert "Fed Funds : " not in text


def test_macro_regions_are_grouped_once_in_text():
    text = "\n".join(format_macro_digest(MACRO_FULL))
    for region in ("BELGIQUE", "ZONE EURO", "ÉTATS-UNIS", "CHANGE"):
        assert text.count(region) == 1


@patch("src.notifications.email_alert.send_email", return_value=True)
def test_immediate_signal_alert_uses_the_same_html_design(mock_send_email):
    result = _watch_item(signal="BUY_OPPORTUNITY_REVIEW", score=82, prob_positive=0.71,
                         symbol="VWCE.DE", data_coverage=0.88)
    assert send_signal_alert(result, 63) is True
    subject, body = mock_send_email.call_args.args
    html = mock_send_email.call_args.kwargs["html_body"]

    assert "Signal à examiner" in subject and "VWCE.DE" in subject
    assert "63 séances" in body
    assert "jamais d’un ordre d’achat" in body
    assert "Opportunité à examiner" in html
    assert "LECTURE DE RECHERCHE" in html
    assert "Score 82/100 ≥ seuil d’examen 75/100." in body


def test_digest_separates_observed_estimated_and_research_sections():
    _, text, html = compose_digest([_watch_item()], "2026-10-31")
    for marker in ("OBSERVÉ", "ESTIMÉ", "LECTURE DE RECHERCHE"):
        assert marker in text and marker in html
    assert text.index("OBSERVÉ") < text.index("ESTIMÉ") < text.index("LECTURE DE RECHERCHE")


def test_probability_shows_horizon_reference_and_currency():
    _, text, _ = compose_digest([_watch_item()], "2026-10-31")
    assert f"Probabilité de rendement positif à 63 séances : 64{NBSP}%" in text
    assert f"Fréquence historique observée : 68{NBSP}%" in text
    assert f"138,25{NBSP}EUR" in text
    assert "Clôture du 30/10/2026" in text


def test_weak_validation_is_disclosed():
    _, text, _ = compose_digest([_watch_item()], "2026-10-31")
    assert "n’a pas fait mieux que la simple fréquence historique" in text


def test_stale_price_is_flagged():
    _, text, _ = compose_digest([_watch_item(as_of="2026-10-20")], "2026-10-31")
    assert "cours ancien de 11 jours" in text
    assert "Cours anciens : VWCE.DE." in text


def test_wording_never_turns_estimates_into_advice():
    forbidden = ["achetez", "achat recommandé", "rendement garanti", "gain assuré",
                 "acheter maintenant", "certitude"]
    for name, payload in scenarios().items():
        if name.startswith("alert"):
            continue
        results, macro = payload
        subject, text, html = compose_digest(results, "2026-10-30", macro)
        blob = (subject + text + html).lower()
        for phrase in forbidden:
            assert phrase not in blob, (name, phrase)


def test_html_is_outlook_and_mobile_friendly():
    _, _, html = compose_digest([_watch_item()], "2026-10-31")
    assert '<!--[if mso]><table role="presentation" width="600"' in html
    assert "max-width:600px" in html
    assert "@media screen and (max-width:620px)" in html
    assert 'name="viewport"' in html


def test_values_from_providers_are_html_escaped():
    _, _, html = compose_digest([_watch_item(name="<script>x</script>")], "2026-10-31")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_insufficient_results_explain_why():
    item = {"id": "eimi", "name": "EM", "symbol": "EIMI.L",
            "status": "INSUFFICIENT_EVIDENCE", "rows": 310}
    _, text, _ = compose_digest([item], "2026-10-31")
    assert "310 lignes exploitables, minimum 500" in text
    history = {"id": "x", "symbol": "X", "status": "INSUFFICIENT_PRICE_HISTORY"}
    _, text, _ = compose_digest([history], "2026-10-31")
    assert "Historique de cours trop court" in text
    assert "DONNÉES DÉGRADÉES" in text

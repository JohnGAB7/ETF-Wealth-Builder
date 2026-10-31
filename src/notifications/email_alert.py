import os
import smtplib
from email.message import EmailMessage
from src.config import get_secret


MACRO_DIGEST_FIELDS = [
    ("ecb_deposit_facility_rate", "Taux de dépôt BCE", "%"),
    ("ecb_usd_per_eur", "Taux de change (USD pour 1 EUR)", ""),
    ("eurostat_hicp_yoy_be", "Inflation HICP Belgique (sur un an)", "%"),
    ("eurostat_hicp_yoy_ea", "Inflation HICP zone euro (sur un an)", "%"),
    ("eurostat_unemployment_be", "Chômage Belgique", "%"),
    ("eurostat_unemployment_ea21", "Chômage zone euro (EA21)", "%"),
    ("eurostat_gdp_qoq_be", "PIB Belgique (variation trimestrielle)", "%"),
    ("eurostat_gdp_qoq_ea21", "PIB zone euro (EA21, variation trimestrielle)", "%"),
    ("us_policy_rate", "Taux directeur américain (Fed Funds)", "%"),
    ("us_cpi_index", "Indice des prix CPI américain", ""),
    ("us_unemployment", "Chômage américain", "%"),
    ("us_10y_yield", "Rendement Treasury américain à 10 ans", "%"),
    ("us_10y_2y_spread", "Écart de taux américain 10 ans - 2 ans", "%"),
    ("us_high_yield_spread", "Spread obligataire High Yield américain", "%"),
]


def send_email(subject: str, body: str) -> bool:
    host = get_secret("SMTP_HOST")
    username = get_secret("SMTP_USERNAME")
    password = get_secret("SMTP_PASSWORD")
    sender = get_secret("EMAIL_FROM")
    recipient = get_secret("EMAIL_TO")
    port = int(os.getenv("SMTP_PORT", "587"))
    if not all([host, username, password, sender, recipient]):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, recipient
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    return True


def format_macro_digest(macro_snapshot: dict | None) -> list[str]:
    """Format the latest cross-region macro snapshot for the daily email."""
    if macro_snapshot is None:
        macro_snapshot = {}

    lines = []
    for key, label, unit in MACRO_DIGEST_FIELDS:
        value = macro_snapshot.get(key)
        observation_date = macro_snapshot.get(key + "_date")
        if value is None:
            lines.append(f"- {label}: indisponible")
            continue
        try:
            formatted = f"{float(value):.2f}{unit}"
        except (TypeError, ValueError):
            formatted = f"{value}{unit}"
        date_note = f" (période: {observation_date})" if observation_date else ""
        lines.append(f"- {label}: {formatted}{date_note}")
    return lines


def send_digest(
    results: list[dict],
    run_date: str,
    macro_snapshot: dict | None = None,
) -> bool:
    lines = [
        f"ETF Wealth Builder — rapport quotidien ({run_date})",
        "",
        "CONTEXTE MACROÉCONOMIQUE (dernières observations publiées)",
        *format_macro_digest(macro_snapshot),
        "",
        "ANALYSE DES ETF",
    ]
    for item in results:
        name = item.get("name", item.get("id", "ETF inconnu"))
        signal = item.get("signal", item.get("status", "N/A"))
        score = item.get("score")
        price = item.get("price")
        lines.append(f"- {name}: {signal}; score={score}; prix={price}")
        if item.get("prob_positive") is not None:
            lines.append(
                f"  P(rendement positif à horizon du modèle)={item['prob_positive']:.1%}"
            )
        if item.get("expected_return") is not None:
            lines.append(
                f"  Rendement conditionnel estimé={item['expected_return']:.2%}"
            )
    lines += [
        "",
        "Les données macro sont descriptives et peuvent être révisées par leurs producteurs.",
        "Les estimations sont incertaines. Aucune garantie de rendement.",
        "Vérifier les données, frais, fiscalité et allocation avant toute décision.",
    ]
    return send_email(
        f"ETF Wealth Builder | Rapport quotidien | {run_date}",
        "\n".join(lines),
    )

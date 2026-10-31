import os
import smtplib
from email.message import EmailMessage
from html import escape

from src.config import get_secret


MACRO_DIGEST_FIELDS = [
    ("ecb_deposit_facility_rate", "Taux de dépôt BCE", "%", "Zone euro", 1),
    ("ecb_usd_per_eur", "USD pour 1 EUR", "", "Marchés des changes", 1),
    ("eurostat_hicp_yoy_be", "Inflation HICP", "%", "Belgique", 1),
    ("eurostat_unemployment_be", "Taux de chômage", "%", "Belgique", 1),
    ("eurostat_gdp_qoq_be", "PIB, variation trimestrielle", "%", "Belgique", 1),
    ("eurostat_hicp_yoy_ea", "Inflation HICP", "%", "Zone euro", 1),
    ("eurostat_unemployment_ea21", "Taux de chômage", "%", "Zone euro", 1),
    ("eurostat_gdp_qoq_ea21", "PIB, variation trimestrielle", "%", "Zone euro", 1),
    ("us_policy_rate", "Taux directeur Fed Funds", "%", "États-Unis", 1),
    ("us_cpi_index", "Indice des prix CPI", "", "États-Unis", 1),
    ("us_unemployment", "Taux de chômage", "%", "États-Unis", 1),
    ("us_10y_yield", "Treasury 10 ans", "%", "États-Unis", 1),
    ("us_10y_2y_spread", "Spread 10 ans - 2 ans", "%", "États-Unis", 1),
    ("us_high_yield_spread", "Spread High Yield", "%", "États-Unis", 1),
]

SIGNAL_LABELS = {
    "BUY_OPPORTUNITY_REVIEW": "Opportunité à examiner",
    "WATCH": "À surveiller",
    "REGULAR_DCA": "DCA habituel",
    "INSUFFICIENT_EVIDENCE": "Données insuffisantes",
    "INSUFFICIENT_PRICE_HISTORY": "Historique insuffisant",
}
SIGNAL_COLORS = {
    "BUY_OPPORTUNITY_REVIEW": ("#e8f4ef", "#176b4d"),
    "WATCH": ("#fff4dc", "#8a5a00"),
    "REGULAR_DCA": ("#eaf1f8", "#315b7d"),
    "INSUFFICIENT_EVIDENCE": ("#f1f3f5", "#596579"),
    "INSUFFICIENT_PRICE_HISTORY": ("#f1f3f5", "#596579"),
}

NAVY = "#102a43"
TEAL = "#087e8b"
GOLD = "#d6a84f"
MUTED = "#627386"
BORDER = "#e4eaf0"
LIGHT = "#f5f8fb"


def send_email(subject: str, body: str, html_body: str | None = None) -> bool:
    """Send a multipart email with a readable plain-text fallback."""
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
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    return True


def _number(value, decimals=2, suffix=""):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}{suffix}".replace(",", " ")
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def _percent(value, decimals=1):
    if value is None:
        return "—"
    try:
        return f"{float(value):.{decimals}%}"
    except (TypeError, ValueError):
        return "—"


def _macro_rows(macro_snapshot: dict | None):
    snapshot = macro_snapshot or {}
    rows = []
    for key, label, unit, region, _ in MACRO_DIGEST_FIELDS:
        value = snapshot.get(key)
        if value is None:
            continue
        observation_date = snapshot.get(key + "_date")
        rows.append({
            "region": region,
            "label": label,
            "value": _number(value, 2, unit),
            "date": str(observation_date) if observation_date else None,
        })
    return rows


def format_macro_digest(macro_snapshot: dict | None) -> list[str]:
    """Return only published macro observations; missing series stay out of the email."""
    rows = _macro_rows(macro_snapshot)
    if not rows:
        return ["Aucune observation macroéconomique disponible pour ce cycle."]

    lines = []
    current_region = None
    for row in rows:
        if row["region"] != current_region:
            current_region = row["region"]
            lines.append(current_region.upper())
        date_note = f" (période: {row['date']})" if row["date"] else ""
        lines.append(f"- {row['label']}: {row['value']}{date_note}")
    available = len(rows)
    total = len(MACRO_DIGEST_FIELDS)
    lines.append(f"{available}/{total} séries macro disponibles; les séries manquantes sont omises.")
    return lines


def _signal_name(item):
    signal = item.get("signal", item.get("status", "N/A"))
    return SIGNAL_LABELS.get(signal, str(signal).replace("_", " ").title())


def _email_shell(title, preheader, date_label, body_html):
    return f"""<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:#eef2f6;font-family:Arial,Helvetica,sans-serif;color:{NAVY};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f6;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:680px;background:#ffffff;border:1px solid {BORDER};border-radius:14px;overflow:hidden;">
<tr><td style="background:{NAVY};padding:26px 30px 24px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
<td style="font-size:12px;letter-spacing:1.8px;text-transform:uppercase;color:#9fd9dc;font-weight:bold;">ETF WEALTH BUILDER</td>
<td align="right" style="font-size:12px;color:#d8e3ec;">{escape(date_label)}</td>
</tr></table>
<div style="font-size:26px;line-height:1.2;font-weight:bold;color:#ffffff;padding-top:16px;">{escape(title)}</div>
<div style="font-size:13px;line-height:1.5;color:#d8e3ec;padding-top:7px;">Votre tableau de bord d’investissement, en un coup d’œil.</div>
</td></tr>
<tr><td style="padding:26px 30px 30px;">{body_html}</td></tr>
<tr><td style="background:{LIGHT};border-top:1px solid {BORDER};padding:18px 30px;">
<div style="font-size:11px;line-height:1.6;color:{MUTED};">
<strong style="color:{NAVY};">Information importante</strong><br>
Ce rapport est un outil de recherche et d’aide à la décision, pas un conseil financier personnalisé ni une instruction d’achat. Les modèles sont incertains et les performances futures ne sont pas garanties. Vérifiez les données, les frais, les spreads, le change, la fiscalité et votre allocation avant toute décision.<br><br>
ETF Wealth Builder · Rapport automatique
</div></td></tr>
</table>
<div style="font-size:10px;color:#8291a1;padding:13px 8px 0;text-align:center;">Vous recevez cet e-mail car les notifications sont activées dans votre configuration.</div>
</td></tr></table></body></html>"""


def _section_title(title, subtitle=None):
    detail = f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">{escape(subtitle)}</div>' if subtitle else ""
    return f'<div style="font-size:16px;font-weight:bold;color:{NAVY};margin:25px 0 12px;">{escape(title)}{detail}</div>'


def _kpi_cell(label, value):
    return f"""<td width="25%" valign="top" style="padding:13px 10px;background:{LIGHT};border:1px solid {BORDER};">
<div style="font-size:10px;line-height:1.4;color:{MUTED};text-transform:uppercase;letter-spacing:.5px;">{escape(label)}</div>
<div style="font-size:21px;line-height:1.25;font-weight:bold;color:{NAVY};padding-top:5px;">{escape(str(value))}</div></td>"""


def _etf_card(item):
    signal = item.get("signal", item.get("status", "N/A"))
    bg, fg = SIGNAL_COLORS.get(signal, ("#f1f3f5", "#596579"))
    name = escape(str(item.get("name", item.get("id", "ETF inconnu"))))
    symbol = escape(str(item.get("symbol", item.get("id", ""))).upper())
    badge = escape(_signal_name(item))
    score = _number(item.get("score"), 0, "/100") if item.get("score") is not None else "—"
    price = _number(item.get("price"), 2)
    probability = _percent(item.get("prob_positive"), 1)
    expected = _percent(item.get("expected_return"), 2)
    drawdown = _percent(item.get("drawdown"), 1)
    coverage = _percent(item.get("data_coverage"), 0)
    metrics = [
        ("Score", score), ("Prix observé", price), ("Probabilité positive", probability),
        ("Rendement estimé", expected), ("Drawdown", drawdown),
    ]
    if item.get("data_coverage") is not None:
        metrics.append(("Couverture des données", coverage))
    cells = "".join(
        f'<td width="{100 // len(metrics)}%" valign="top" style="padding:10px 7px 8px 0;">'
        f'<div style="font-size:10px;color:{MUTED};line-height:1.4;">{escape(label)}</div>'
        f'<div style="font-size:14px;font-weight:bold;color:{NAVY};padding-top:3px;">{escape(value)}</div></td>'
        for label, value in metrics
    )
    extras = []
    if item.get("valuation_coverage_weight") is not None:
        extras.append(
            "Couverture fondamentale US/Canada: " +
            _percent(item.get("valuation_coverage_weight"), 0) +
            " du poids total de l’ETF"
        )
    if item.get("analyst", {}).get("analyst_coverage_weight") is not None:
        extras.append(
            "Couverture des recommandations analystes: " +
            _percent(item["analyst"].get("analyst_coverage_weight"), 0)
        )
    if item.get("rows") is not None:
        extras.append(f"Observations utilisées par le modèle: {item['rows']}")
    extra_html = ""
    if extras:
        extra_html = f'<div style="font-size:11px;line-height:1.7;color:{MUTED};border-top:1px solid {BORDER};margin-top:8px;padding-top:8px;">{ "<br>".join(escape(x) for x in extras) }</div>'
    return f"""<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid {BORDER};border-radius:10px;margin:0 0 12px;">
<tr><td style="padding:15px 16px 8px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
<td valign="top"><div style="font-size:15px;font-weight:bold;color:{NAVY};">{name}</div>
<div style="font-size:11px;color:{MUTED};padding-top:3px;">{symbol}</div></td>
<td align="right" valign="top"><span style="display:inline-block;background:{bg};color:{fg};border-radius:20px;padding:6px 10px;font-size:10px;font-weight:bold;">{badge}</span></td>
</tr></table>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;"><tr>{cells}</tr></table>
{extra_html}
</td></tr></table>"""


def _macro_html(macro_snapshot):
    rows = _macro_rows(macro_snapshot)
    if not rows:
        return (
            f'<div style="padding:14px 16px;background:{LIGHT};border-radius:8px;'
            f'font-size:12px;color:{MUTED};">Aucune observation macroéconomique disponible pour ce cycle.</div>'
        )
    grouped = {}
    for row in rows:
        grouped.setdefault(row["region"], []).append(row)
    blocks = []
    for region, region_rows in grouped.items():
        cells = []
        for row in region_rows:
            date = f'<div style="font-size:10px;color:{MUTED};padding-top:2px;">{escape(row["date"])}</div>' if row["date"] else ""
            cells.append(
                f'<tr><td style="padding:9px 8px 9px 0;border-bottom:1px solid {BORDER};font-size:12px;color:{NAVY};">{escape(row["label"])}</td>'
                f'<td align="right" style="padding:9px 0;border-bottom:1px solid {BORDER};font-size:12px;font-weight:bold;color:{NAVY};white-space:nowrap;">{escape(row["value"])}{date}</td></tr>'
            )
        blocks.append(
            f'<td width="50%" valign="top" style="padding:0 14px 14px 0;">'
            f'<div style="font-size:12px;letter-spacing:.6px;text-transform:uppercase;font-weight:bold;color:{TEAL};margin-bottom:4px;">{escape(region)}</div>'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{"".join(cells)}</table></td>'
        )
    grid_rows = []
    for i in range(0, len(blocks), 2):
        right = blocks[i + 1] if i + 1 < len(blocks) else '<td width="50%"></td>'
        grid_rows.append(f'<tr>{blocks[i]}{right}</tr>')
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
        f'{"".join(grid_rows)}</table>'
        f'<div style="font-size:10px;color:{MUTED};padding-top:5px;">{len(rows)}/{len(MACRO_DIGEST_FIELDS)} séries disponibles. '
        'Les séries sans nouvelle observation sont volontairement masquées.</div>'
    )


def send_digest(
    results: list[dict],
    run_date: str,
    macro_snapshot: dict | None = None,
) -> bool:
    results = results or []
    counts = {
        "BUY_OPPORTUNITY_REVIEW": 0,
        "WATCH": 0,
        "REGULAR_DCA": 0,
        "INSUFFICIENT_EVIDENCE": 0,
        "INSUFFICIENT_PRICE_HISTORY": 0,
    }
    for item in results:
        signal = item.get("signal", item.get("status", "N/A"))
        counts[signal] = counts.get(signal, 0) + 1

    opportunities = counts["BUY_OPPORTUNITY_REVIEW"]
    watches = counts["WATCH"]
    if opportunities:
        intro = f"{opportunities} opportunité(s) à examiner ressort(ent) de l’analyse du jour. Ce signal invite à approfondir, pas à acheter automatiquement."
    elif watches:
        intro = f"{watches} ETF(s) méritent une surveillance particulière. Aucun signal d’opportunité prioritaire n’a été confirmé."
    else:
        intro = "Aucun signal d’opportunité prioritaire aujourd’hui. Le suivi régulier et le DCA restent le scénario de référence."

    summary_labels = [
        ("À examiner", opportunities),
        ("À surveiller", watches),
        ("DCA habituel", counts["REGULAR_DCA"]),
        ("Données limitées", counts["INSUFFICIENT_EVIDENCE"] + counts["INSUFFICIENT_PRICE_HISTORY"]),
    ]
    summary_cells = "".join(_kpi_cell(label, value) for label, value in summary_labels)
    html_parts = [
        f'<div style="font-size:14px;line-height:1.65;color:{NAVY};margin-bottom:17px;">{escape(intro)}</div>',
        f'<table role="presentation" width="100%" cellspacing="6" cellpadding="0" border="0"><tr>{summary_cells}</tr></table>',
        _section_title("Analyse des ETF", "Une fiche par fonds suivi · les signaux sont des alertes de recherche"),
    ]
    text_lines = [
        f"ETF WEALTH BUILDER — RAPPORT QUOTIDIEN | {run_date}",
        "=" * 58,
        intro,
        "",
        "SYNTHÈSE",
        f"À examiner : {opportunities}",
        f"À surveiller : {watches}",
        f"DCA habituel : {counts['REGULAR_DCA']}",
        f"Données limitées : {counts['INSUFFICIENT_EVIDENCE'] + counts['INSUFFICIENT_PRICE_HISTORY']}",
        "",
        "ANALYSE DES ETF",
    ]

    if results:
        for item in results:
            signal = item.get("signal", item.get("status", "N/A"))
            title = item.get("name", item.get("id", "ETF inconnu"))
            symbol = item.get("symbol", item.get("id", ""))
            html_parts.append(_etf_card(item))
            text_lines.extend([
                "",
                f"{title} ({str(symbol).upper()})",
                f"Statut : {_signal_name(item)}",
                f"Score : {_number(item.get('score'), 0, '/100') if item.get('score') is not None else '—'}",
                f"Prix observé : {_number(item.get('price'), 2)}",
                f"Probabilité de rendement positif : {_percent(item.get('prob_positive'), 1)}",
                f"Rendement conditionnel estimé : {_percent(item.get('expected_return'), 2)}",
                f"Drawdown : {_percent(item.get('drawdown'), 1)}",
            ])
            if item.get("valuation_coverage_weight") is not None:
                text_lines.append(
                    "Couverture fondamentale US/Canada : " +
                    _percent(item.get("valuation_coverage_weight"), 0) +
                    " du poids total de l’ETF"
                )
            if signal in ("INSUFFICIENT_EVIDENCE", "INSUFFICIENT_PRICE_HISTORY"):
                text_lines.append("Le modèle ne dispose pas d'éléments suffisants pour produire un signal exploitable.")
    else:
        html_parts.append(
            f'<div style="padding:16px;background:{LIGHT};border-radius:8px;color:{MUTED};font-size:13px;">'
            'Aucun ETF n’a été analysé pendant ce cycle.</div>'
        )
        text_lines.append("Aucun ETF n’a été analysé pendant ce cycle.")

    html_parts.extend([
        _section_title("Contexte macroéconomique", "Dernières observations publiées · les dates indiquent la période des données"),
        _macro_html(macro_snapshot),
        f'<div style="font-size:11px;line-height:1.6;color:{MUTED};padding-top:15px;">'
        'Les valeurs macroéconomiques sont descriptives et peuvent être révisées par leurs producteurs. '
        'La valorisation des constituants ne représente pas la juste valeur de l’ETF entier; sa couverture est indiquée séparément.</div>',
    ])
    text_lines.extend(["", "CONTEXTE MACROÉCONOMIQUE", *format_macro_digest(macro_snapshot)])
    text_lines.extend([
        "",
        "À RETENIR",
        "- Un score ou une probabilité n'est pas une prévision certaine.",
        "- La valorisation fondamentale ne couvre que les constituants éligibles US/Canada et ne donne pas la juste valeur de l’ETF.",
        "- Le modèle reste un outil de recherche en cours de validation; consulter la gouvernance du modèle avant toute décision.",
        "",
        "Vérifier également les frais, le spread, le change, la fiscalité belge et l’allocation globale.",
    ])

    html_body = _email_shell(
        "Votre point quotidien sur les ETF",
        intro,
        run_date,
        "".join(html_parts),
    )
    subject = f"ETF Wealth Builder | Point quotidien | {run_date}"
    return send_email(subject, "\n".join(text_lines), html_body=html_body)


def send_signal_alert(result: dict, horizon_days: int) -> bool:
    """Send a formatted alert when an ETF meets the review threshold."""
    name = str(result.get("name", result.get("id", "ETF")))
    symbol = str(result.get("symbol", result.get("id", ""))).upper()
    score = _number(result.get("score"), 0, "/100")
    probability = _percent(result.get("prob_positive"), 1)
    expected = _percent(result.get("expected_return"), 2)
    price = _number(result.get("price"), 2)
    drawdown = _percent(result.get("drawdown"), 1)
    as_of = str(result.get("as_of", ""))
    coverage = _percent(result.get("data_coverage"), 0)
    valuation_coverage = _percent(result.get("valuation_coverage_weight"), 0)
    subject = f"ETF Wealth Builder | Signal à examiner | {symbol}"

    intro = f"{name} a franchi les seuils de suivi du modèle. Il s’agit d’une invitation à vérifier les données et le contexte, jamais d’un ordre d’achat."
    metrics = [
        ("Score", score), ("Probabilité positive", probability),
        ("Rendement estimé", expected), ("Prix observé", price),
    ]
    cells = "".join(_kpi_cell(label, value) for label, value in metrics)
    detail_html = f"""
<div style="font-size:14px;line-height:1.65;color:{NAVY};">{escape(intro)}</div>
<div style="margin:12px 0 8px;"><span style="display:inline-block;background:#e8f4ef;color:#176b4d;border-radius:20px;padding:7px 12px;font-size:11px;font-weight:bold;">OPPORTUNITÉ À EXAMINER</span></div>
<table role="presentation" width="100%" cellspacing="6" cellpadding="0" border="0"><tr>{cells}</tr></table>
{_section_title("Éléments de contexte")}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
<tr><td style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;color:{MUTED};">Drawdown courant</td><td align="right" style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;font-weight:bold;">{escape(drawdown)}</td></tr>
<tr><td style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;color:{MUTED};">Couverture des données</td><td align="right" style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;font-weight:bold;">{escape(coverage)}</td></tr>
<tr><td style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;color:{MUTED};">Couverture fondamentale US/Canada</td><td align="right" style="padding:8px 0;border-bottom:1px solid {BORDER};font-size:12px;font-weight:bold;">{escape(valuation_coverage)} du poids total de l’ETF</td></tr>
<tr><td style="padding:8px 0;font-size:12px;color:{MUTED};">Date du cours</td><td align="right" style="padding:8px 0;font-size:12px;font-weight:bold;">{escape(as_of)}</td></tr>
</table>
<div style="font-size:11px;line-height:1.6;color:{MUTED};padding-top:14px;">Horizon du modèle : {int(horizon_days)} jours. Le rendement conditionnel estimé et la probabilité sont des estimations statistiques, non des garanties.</div>
"""
    text_body = "\n".join([
        "ETF WEALTH BUILDER — SIGNAL À EXAMINER",
        "=" * 48,
        intro,
        "",
        f"ETF : {name} ({symbol})",
        f"Score : {score}",
        f"Probabilité de rendement positif à {int(horizon_days)} jours : {probability}",
        f"Rendement conditionnel estimé : {expected}",
        f"Prix observé : {price}",
        f"Drawdown courant : {drawdown}",
        f"Couverture des données : {coverage}",
        f"Couverture fondamentale US/Canada : {valuation_coverage} du poids total de l’ETF",
        f"Date du cours : {as_of}",
        "",
        "Ce signal est une invitation à approfondir, pas un ordre d’achat.",
        "Vérifier les données, les frais, les spreads, le change, la fiscalité et l’allocation.",
    ])
    return send_email(
        subject,
        text_body,
        html_body=_email_shell(
            f"Signal à examiner · {symbol}",
            intro,
            as_of,
            detail_html,
        ),
    )

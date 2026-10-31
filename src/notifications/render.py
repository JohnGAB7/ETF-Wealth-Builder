"""Render an e-mail view (see view_model.py) to HTML and plain text.

HTML constraints, chosen for Gmail, Outlook (Windows, Word engine), Apple Mail
and mobile clients:
- table layout, inline styles, 600 px single column;
- an MSO "ghost table" fixes the width in Outlook, which ignores max-width;
- one <style> block only for progressive enhancement (mobile padding);
  the layout stays readable if a client strips it;
- label/value rows instead of multi-column grids, so nothing has to stack;
- body text >= 14 px, secondary text >= 12 px.
"""
from html import escape

NAVY = "#102a43"
INK = "#1f2d3d"
MUTED = "#52606d"
BORDER = "#d9e2ec"
LIGHT = "#f5f7fa"
PAGE = "#eef2f6"
FONT = "Arial, Helvetica, sans-serif"

TONES = {  # background, foreground, border
    "positive": ("#e3f4ec", "#14573d", "#9fd3b9"),
    "warning": ("#fff4d6", "#7a4f00", "#f0cf80"),
    "info": ("#e6eff8", "#24496b", "#a9c4de"),
    "neutral": ("#eef1f4", "#46525e", "#cdd5dd"),
    "complete": ("#e3f4ec", "#14573d", "#9fd3b9"),
    "partial": ("#fff4d6", "#7a4f00", "#f0cf80"),
    "degraded": ("#fde8e8", "#8a1f1f", "#f0a8a8"),
}
SECTION_TAGS = {
    "observed": ("OBSERVÉ", "Données de marché publiées", "#46525e"),
    "estimated": ("ESTIMÉ", "Modèle statistique, résultat incertain", "#5b3f8c"),
    "research": ("LECTURE DE RECHERCHE", "Règles de décision appliquées", "#14573d"),
}

_TABLE = 'role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"'


def _e(value) -> str:
    return escape("" if value is None else str(value))


def _badge(label, tone):
    bg, fg, bd = TONES.get(tone, TONES["neutral"])
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {bd};'
            f'border-radius:12px;padding:3px 9px;font-size:12px;font-weight:bold;'
            f'white-space:nowrap;">{_e(label)}</span>')


def _heading(text, sub=None):
    detail = (f'<div style="font-size:13px;color:{MUTED};font-weight:normal;padding-top:3px;">'
              f'{_e(sub)}</div>') if sub else ""
    return (f'<tr><td class="px" style="padding:26px 28px 10px;font-family:{FONT};">'
            f'<div style="font-size:18px;line-height:1.3;font-weight:bold;color:{NAVY};">'
            f'{_e(text)}</div>{detail}</td></tr>')


def _row(content, padding="0 28px 12px"):
    return f'<tr><td class="px" style="padding:{padding};font-family:{FONT};">{content}</td></tr>'


def _kv_rows(rows):
    out = []
    for i, row in enumerate(rows):
        border = f"border-top:1px solid {BORDER};" if i else ""
        note = (f'<div style="font-size:12px;line-height:1.45;color:{MUTED};padding-top:2px;">'
                f'{_e(row.get("note"))}</div>') if row.get("note") else ""
        out.append(
            f'<tr><td valign="top" style="{border}padding:8px 10px 8px 0;font-size:14px;'
            f'line-height:1.4;color:{INK};">{_e(row["label"])}{note}</td>'
            f'<td valign="top" align="right" style="{border}padding:8px 0;font-size:16px;'
            f'line-height:1.4;font-weight:bold;color:{NAVY};white-space:nowrap;">'
            f'{_e(row["value"])}</td></tr>')
    return f'<table {_TABLE}>{"".join(out)}</table>'


def _block(kind, inner):
    tag, sub, colour = SECTION_TAGS[kind]
    return (f'<div style="margin-top:14px;">'
            f'<div style="font-size:11px;letter-spacing:1px;font-weight:bold;color:{colour};">'
            f'{tag} <span style="font-weight:normal;letter-spacing:0;color:{MUTED};">'
            f'· {_e(sub)}</span></div>'
            f'<div style="border-left:3px solid {colour};padding:2px 0 2px 12px;margin-top:6px;">'
            f'{inner}</div></div>')


def _bullets(items, size=14, colour=INK):
    if not items:
        return ""
    lis = "".join(
        f'<tr><td valign="top" style="width:14px;font-size:{size}px;line-height:1.5;'
        f'color:{MUTED};">•</td><td style="font-size:{size}px;line-height:1.5;color:{colour};'
        f'padding-bottom:4px;">{_e(item)}</td></tr>' for item in items)
    return f'<table {_TABLE}>{lis}</table>'


def _card(card):
    blocks = []
    if card["observed"]:
        blocks.append(_block("observed", _kv_rows(card["observed"])))
    if card["estimated"]:
        inner = _kv_rows(card["estimated"])
        quality = card.get("model_quality")
        if quality:
            bg, fg, _ = TONES.get(quality["tone"], TONES["neutral"])
            inner += (f'<div style="background:{bg};color:{fg};border-radius:6px;padding:9px 11px;'
                      f'margin-top:6px;font-size:13px;line-height:1.5;">'
                      f'<strong>Validation :</strong> {_e(quality["summary"])}<br>'
                      f'{_e(quality["verdict"])}'
                      + (f'<br><span style="color:{MUTED};">{_e(quality["period"])}</span>'
                         if quality.get("period") else "") + '</div>')
        blocks.append(_block("estimated", inner))
    research = (f'<div style="font-size:14px;line-height:1.5;color:{INK};padding:4px 0 6px;">'
                f'Statut : <strong>{_e(card["status_label"])}</strong></div>'
                + _bullets(card["reasons"], 13))
    blocks.append(_block("research", research))
    if card["quality"]:
        blocks.append(
            f'<div style="margin-top:14px;padding-top:10px;border-top:1px solid {BORDER};">'
            f'<div style="font-size:12px;font-weight:bold;color:{MUTED};padding-bottom:4px;">'
            f'Qualité et couverture des données</div>{_bullets(card["quality"], 12, MUTED)}</div>')
    ident = card["symbol"] + (f' · {card["isin"]}' if card.get("isin") else "")
    return (
        f'<table {_TABLE} style="border:1px solid {BORDER};border-radius:8px;margin-bottom:14px;">'
        f'<tr><td style="padding:16px 16px 14px;font-family:{FONT};">'
        f'<table {_TABLE}><tr>'
        f'<td valign="top"><div style="font-size:16px;line-height:1.35;font-weight:bold;'
        f'color:{NAVY};">{_e(card["name"])}</div>'
        f'<div style="font-size:12px;color:{MUTED};padding-top:2px;">{_e(ident)}</div></td>'
        f'<td valign="top" align="right" style="padding-left:8px;">'
        f'{_badge(card["status_label"], card["tone"])}</td></tr></table>'
        f'<div style="font-size:14px;line-height:1.5;color:{INK};padding-top:10px;">'
        f'{_e(card["headline"])}</div>'
        + (f'<div style="font-size:13px;line-height:1.5;padding-top:4px;color:'
           f'{"#14573d" if card["change"]["changed"] else MUTED};'
           f'{"font-weight:bold;" if card["change"]["changed"] else ""}">'
           f'{_e(card["change"]["text"])}</div>' if card.get("change") else "")
        + "".join(blocks) + '</td></tr></table>')


def _counts(counts):
    cells = []
    for count in counts:
        bg, fg, bd = TONES.get(count["tone"], TONES["neutral"])
        cells.append(
            f'<td width="25%" valign="top" align="center" style="padding:3px;">'
            f'<div style="background:{bg};border:1px solid {bd};border-radius:6px;padding:9px 4px;">'
            f'<div style="font-size:22px;line-height:1.2;font-weight:bold;color:{fg};">'
            f'{_e(count["value"])}</div>'
            f'<div style="font-size:12px;line-height:1.3;color:{fg};">{_e(count["label"])}</div>'
            f'</div></td>')
    return f'<table {_TABLE}><tr>{"".join(cells)}</tr></table>'


def _overview(rows):
    head = (f'<tr><td style="font-size:12px;color:{MUTED};padding:0 0 6px;">ETF</td>'
            f'<td style="font-size:12px;color:{MUTED};padding:0 0 6px;" align="right">Statut</td>'
            f'<td style="font-size:12px;color:{MUTED};padding:0 0 6px 10px;" align="right">Score</td></tr>')
    body = "".join(
        f'<tr><td style="border-top:1px solid {BORDER};padding:8px 0;font-size:14px;color:{NAVY};">'
        f'<strong>{_e(r["symbol"])}</strong>'
        + (f' <span style="color:{MUTED};font-size:12px;">{_e(r["change"])}</span>'
           if r.get("change") else "") + '</td>'
        f'<td align="right" style="border-top:1px solid {BORDER};padding:8px 0;">'
        f'{_badge(r["status_label"], r["tone"])}</td>'
        f'<td align="right" style="border-top:1px solid {BORDER};padding:8px 0 8px 10px;'
        f'font-size:14px;color:{NAVY};white-space:nowrap;">{_e(r["score"])}</td></tr>'
        for r in rows)
    return f'<table {_TABLE}>{head}{body}</table>'


def _macro(macro):
    if not macro["available"]:
        return (f'<div style="background:{LIGHT};border-radius:6px;padding:12px 14px;'
                f'font-size:14px;color:{MUTED};">Aucune observation macroéconomique disponible '
                f'pour ce cycle ({macro["total"]} séries interrogées).</div>')
    parts = []
    for group in macro["groups"]:
        rows = [{"label": r["label"], "value": r["value"], "note": f'Période : {r["period"]}'}
                for r in group["rows"]]
        parts.append(f'<div style="font-size:12px;letter-spacing:1px;font-weight:bold;color:#0b6e78;'
                     f'padding:12px 0 2px;">{_e(group["region"].upper())}</div>{_kv_rows(rows)}')
    footer = f'{macro["available"]}/{macro["total"]} séries disponibles.'
    if macro["missing"]:
        footer += " Indisponibles ce jour : " + ", ".join(macro["missing"]) + "."
    if macro.get("old"):
        footer += " Observations anciennes : " + ", ".join(macro["old"]) + "."
    parts.append(f'<div style="font-size:12px;line-height:1.5;color:{MUTED};padding-top:8px;">'
                 f'{_e(footer)} Valeurs descriptives, susceptibles d’être révisées.</div>')
    return "".join(parts)


def render_html(view: dict) -> str:
    rows = []
    status = view.get("data_status")
    if status:
        bg, fg, bd = TONES[status["level"]]
        rows.append(_row(
            f'<div style="background:{bg};border:1px solid {bd};border-radius:6px;'
            f'padding:10px 14px;color:{fg};font-size:13px;line-height:1.5;">'
            f'<strong>{_e(status["label"])}</strong> · {_e(" ".join(status["reasons"]))}</div>',
            "20px 28px 0"))
    summary = view["summary"]
    rows.append(_heading("Synthèse" if view["kind"] == "digest" else "Pourquoi cette alerte"))
    rows.append(_row(f'<div style="font-size:16px;line-height:1.5;color:{INK};">'
                     f'{_e(summary["headline"])}</div>'))
    if summary["counts"]:
        rows.append(_row(_counts(summary["counts"])))
    if summary["bullets"]:
        rows.append(_row(_bullets(summary["bullets"])))
    if len(view["overview"]) > 1:
        rows.append(_heading("Vue d’ensemble"))
        rows.append(_row(_overview(view["overview"])))
    rows.append(_heading("Fiches ETF" if view["kind"] == "digest" else "Fiche ETF",
                         "Observé, estimé et lecture de recherche sont séparés"))
    if view["etfs"]:
        rows.append(_row("".join(_card(c) for c in view["etfs"])))
    else:
        rows.append(_row(f'<div style="background:{LIGHT};padding:12px 14px;font-size:14px;'
                         f'color:{MUTED};border-radius:6px;">Aucun ETF n’a été analysé pendant '
                         f'ce cycle.</div>'))
    if view.get("macro") is not None:
        rows.append(_heading("Contexte macroéconomique",
                             "Dernières observations publiées, avec leur période"))
        rows.append(_row(_macro(view["macro"])))
    rows.append(_heading("Méthode et limites"))
    rows.append(_row(_bullets(view["methodology"], 13, MUTED), "0 28px 24px"))

    body = "".join(rows)
    return f"""<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{_e(view["title"])}</title>
<!--[if mso]><style>table,td,div,p,span{{font-family:Arial,Helvetica,sans-serif !important;}}</style><![endif]-->
<style>
body{{margin:0;padding:0;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}}
table{{border-collapse:collapse;}}
@media screen and (max-width:620px){{
  .px{{padding-left:14px !important;padding-right:14px !important;}}
  .outer{{padding:0 !important;}}
}}
</style>
</head>
<body style="margin:0;padding:0;background:{PAGE};">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{_e(view["preheader"])}{"&#8199;&#65279;&#847; " * 40}</div>
<table {_TABLE} style="background:{PAGE};"><tr><td class="outer" align="center" style="padding:20px 10px;">
<!--[if mso]><table role="presentation" width="600" align="center" cellspacing="0" cellpadding="0" border="0"><tr><td><![endif]-->
<table {_TABLE} style="max-width:600px;background:#ffffff;border:1px solid {BORDER};">
<tr><td class="px" style="background:{NAVY};padding:20px 28px;font-family:{FONT};">
<table {_TABLE}><tr>
<td style="font-size:12px;letter-spacing:1.5px;font-weight:bold;color:#9fd9dc;">ETF WEALTH BUILDER</td>
<td align="right" style="font-size:13px;color:#d8e3ec;">{_e(view["date_label"])}</td>
</tr></table>
<div style="font-size:24px;line-height:1.25;font-weight:bold;color:#ffffff;padding-top:12px;">{_e(view["title"])}</div>
<div style="font-size:14px;line-height:1.5;color:#d8e3ec;padding-top:4px;">{_e(view["subtitle"])}</div>
</td></tr>
{body}
<tr><td class="px" style="background:{LIGHT};border-top:1px solid {BORDER};padding:16px 28px;font-family:{FONT};">
<div style="font-size:12px;line-height:1.6;color:{MUTED};"><strong style="color:{NAVY};">Information importante.</strong> {_e(view["disclaimer"])}</div>
</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
<div style="font-family:{FONT};font-size:12px;color:#7b8794;padding:12px 8px 0;text-align:center;">Message automatique d’ETF Wealth Builder, envoyé car les notifications sont activées dans votre configuration.</div>
</td></tr></table>
</body>
</html>"""


def render_text(view: dict) -> str:
    title = f"ETF WEALTH BUILDER — {view['title'].upper()} — {view['date_label']}"
    lines = [title, "=" * min(len(title), 72), ""]
    status = view.get("data_status")
    if status:
        lines += [f"[{status['label'].upper()}] " + " ".join(status["reasons"]), ""]
    summary = view["summary"]
    lines += ["SYNTHÈSE" if view["kind"] == "digest" else "POURQUOI CETTE ALERTE",
              summary["headline"]]
    if summary["counts"]:
        lines.append(" | ".join(f"{c['label']} : {c['value']}" for c in summary["counts"]))
    lines += [f"- {b}" for b in summary["bullets"]]

    for card in view["etfs"]:
        ident = card["symbol"] + (f" · {card['isin']}" if card.get("isin") else "")
        lines += ["", "-" * 60, f"{card['name']} ({ident})",
                  f"Statut : {card['status_label']} | Score : {card['score']}", card["headline"]]
        if card.get("change"):
            lines.append(card["change"]["text"])
        if card["observed"]:
            lines.append("  OBSERVÉ")
            lines += [f"  - {r['label']} : {r['value']}" + (f" ({r['note']})" if r.get("note") else "")
                      for r in card["observed"]]
        if card["estimated"]:
            lines.append("  ESTIMÉ (modèle statistique, résultat incertain)")
            lines += [f"  - {r['label']} : {r['value']}" + (f" ({r['note']})" if r.get("note") else "")
                      for r in card["estimated"]]
            quality = card.get("model_quality")
            if quality:
                lines.append(f"  - Validation : {quality['summary']}. {quality['verdict']}"
                             + (f" {quality['period']}" if quality.get("period") else ""))
        lines.append("  LECTURE DE RECHERCHE")
        lines += [f"  - {reason}" for reason in card["reasons"]]
        if card["quality"]:
            lines.append("  QUALITÉ ET COUVERTURE DES DONNÉES")
            lines += [f"  - {q}" for q in card["quality"]]
    if not view["etfs"]:
        lines += ["", "Aucun ETF n’a été analysé pendant ce cycle."]

    macro = view.get("macro")
    if macro is not None:
        lines += ["", "CONTEXTE MACROÉCONOMIQUE"]
        if not macro["available"]:
            lines.append(f"Aucune observation macroéconomique disponible pour ce cycle "
                         f"({macro['total']} séries interrogées).")
        for group in macro["groups"]:
            lines.append(group["region"].upper())
            lines += [f"- {r['label']} : {r['value']} (période : {r['period']})" for r in group["rows"]]
        if macro["available"]:
            lines.append(f"{macro['available']}/{macro['total']} séries disponibles.")
            if macro["missing"]:
                lines.append("Indisponibles ce jour : " + ", ".join(macro["missing"]) + ".")
            if macro.get("old"):
                lines.append("Observations anciennes : " + ", ".join(macro["old"]) + ".")

    lines += ["", "MÉTHODE ET LIMITES"] + [f"- {note}" for note in view["methodology"]]
    lines += ["", "INFORMATION IMPORTANTE", view["disclaimer"]]
    return "\n".join(lines) + "\n"

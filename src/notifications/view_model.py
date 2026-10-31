"""Build one presentation-neutral view of a daily digest or a signal alert.

The HTML and plain-text renderers both consume this view, so the two versions
of an e-mail can never disagree. This module only *describes* results: it never
changes a signal, a threshold or a value, and it never fills a missing value.

Three kinds of content are kept apart on purpose:
- observed: market or macro data as published (price, drawdown, RSI);
- estimated: statistical model outputs, always labelled as uncertain;
- research reading: the rule-based status and the reasons behind it.
"""
from datetime import date

from src.notifications.formatting import (
    MISSING, NBSP, fr_date, fr_number, fr_percent, fr_period, fr_points, fr_score,
    parse_day,
)
from src.strategy.opportunity import WATCH_SCORE_THRESHOLD

# key, label, unit ("%" = value already in percent), region, decimals, frequency
MACRO_DIGEST_FIELDS = [
    ("eurostat_hicp_yoy_be", "Inflation HICP (sur un an)", "%", "Belgique", 1, "M"),
    ("eurostat_unemployment_be", "Taux de chômage", "%", "Belgique", 1, "M"),
    ("eurostat_gdp_qoq_be", "PIB, variation trimestrielle", "%", "Belgique", 1, "Q"),
    ("ecb_deposit_facility_rate", "Taux de dépôt BCE", "%", "Zone euro", 2, "D"),
    ("eurostat_hicp_yoy_ea", "Inflation HICP (sur un an)", "%", "Zone euro", 1, "M"),
    ("eurostat_unemployment_ea21", "Taux de chômage", "%", "Zone euro", 1, "M"),
    ("eurostat_gdp_qoq_ea21", "PIB, variation trimestrielle", "%", "Zone euro", 1, "Q"),
    ("us_policy_rate", "Taux directeur Fed Funds", "%", "États-Unis", 2, "M"),
    ("us_cpi_yoy", "Inflation CPI (sur un an)", "%", "États-Unis", 1, "M"),
    ("us_unemployment", "Taux de chômage", "%", "États-Unis", 1, "M"),
    ("us_10y_yield", "Rendement Treasury 10 ans", "%", "États-Unis", 2, "D"),
    ("us_10y_2y_spread", "Écart 10 ans - 2 ans", "%", "États-Unis", 2, "D"),
    ("us_high_yield_spread", "Spread High Yield", "%", "États-Unis", 2, "D"),
    ("ecb_usd_per_eur", "USD pour 1 EUR (référence BCE)", "", "Change", 4, "D"),
]

SIGNAL_LABELS = {
    "BUY_OPPORTUNITY_REVIEW": "Opportunité à examiner",
    "WATCH": "À surveiller",
    "REGULAR_DCA": "DCA habituel",
    "INSUFFICIENT_EVIDENCE": "Données insuffisantes",
    "INSUFFICIENT_PRICE_HISTORY": "Historique insuffisant",
}
# Tone drives colours only; it never changes the status.
SIGNAL_TONES = {
    "BUY_OPPORTUNITY_REVIEW": "positive",
    "WATCH": "warning",
    "REGULAR_DCA": "info",
    "INSUFFICIENT_EVIDENCE": "neutral",
    "INSUFFICIENT_PRICE_HISTORY": "neutral",
}
STATUS_ORDER = ["BUY_OPPORTUNITY_REVIEW", "WATCH", "REGULAR_DCA",
                "INSUFFICIENT_EVIDENCE", "INSUFFICIENT_PRICE_HISTORY"]

# Default when a result does not carry max_price_age_days (strategy.yaml value).
STALE_PRICE_DAYS = 5
# A macro observation older than this (days between period start and run date)
# is flagged as old. Display only; publication lags are included.
MACRO_MAX_AGE_DAYS = {"D": 10, "M": 100, "Q": 240}

DEFAULT_THRESHOLDS = {
    "score_threshold": 75,
    "probability_threshold": 0.62,
    "min_coverage": 0.70,
    "min_training_rows": 500,
    "horizon_days": 63,
}

DISCLAIMER = (
    "Ce rapport est un outil personnel de recherche et d’aide à la décision. Il ne "
    "constitue ni un conseil financier personnalisé ni une instruction d’achat ou de "
    "vente. Les probabilités et rendements affichés sont des estimations statistiques "
    "incertaines, pas des garanties. Vérifiez les données, les frais, les spreads, le "
    "change, la fiscalité belge et votre allocation avant toute décision."
)

METHODOLOGY_NOTES = [
    "Les estimations proviennent d’un modèle de recherche entraîné sur des "
    "indicateurs techniques. Sa validation repose sur une seule période de test "
    "chronologique, sans purge ni embargo : elle est préliminaire.",
    "La valorisation des constituants (ValueInvesting.io, actions US et Canada "
    "uniquement) est un indicateur partiel ; elle ne représente pas la juste valeur "
    "de l’ETF entier. Sa couverture est exprimée en poids total de l’ETF.",
    "Les données macroéconomiques sont affichées avec leur période d’observation. "
    "Elles peuvent être révisées par leurs producteurs et ne sont pas encore "
    "intégrées au modèle.",
    "Les frais, spreads, effets de change et la fiscalité belge ne sont pas encore "
    "intégrés aux calculs.",
]


def thresholds_from_strategy(strategy: dict | None) -> dict:
    strategy = strategy or {}
    return {
        "score_threshold": strategy.get("opportunity_score_threshold",
                                        DEFAULT_THRESHOLDS["score_threshold"]),
        "probability_threshold": strategy.get("probability_buy_threshold",
                                              DEFAULT_THRESHOLDS["probability_threshold"]),
        "min_coverage": strategy.get("minimum_data_coverage",
                                     DEFAULT_THRESHOLDS["min_coverage"]),
        "min_training_rows": strategy.get("minimum_training_rows",
                                          DEFAULT_THRESHOLDS["min_training_rows"]),
        "horizon_days": strategy.get("primary_horizon_days",
                                     DEFAULT_THRESHOLDS["horizon_days"]),
    }


def status_of(item: dict) -> str:
    return str(item.get("signal") or item.get("status") or "INSUFFICIENT_EVIDENCE")


def status_label(status: str) -> str:
    return SIGNAL_LABELS.get(status, status.replace("_", " ").capitalize())


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


# ---------------------------------------------------------------- reasons
def signal_reasons(item: dict, th: dict) -> list[str]:
    """Explain, in plain language, which rule produced the status."""
    status = status_of(item)
    score, prob, coverage = _num(item.get("score")), _num(item.get("prob_positive")), \
        _num(item.get("data_coverage"))
    s_thr, p_thr, c_min = th["score_threshold"], th["probability_threshold"], th["min_coverage"]

    if status == "INSUFFICIENT_PRICE_HISTORY":
        return ["Historique de cours trop court ou indisponible : aucun indicateur ni "
                "modèle n’a été calculé."]
    if status == "INSUFFICIENT_EVIDENCE":
        if score is None:
            rows = item.get("rows")
            rows_text = f" ({rows} lignes exploitables, minimum {th['min_training_rows']})" \
                if rows is not None else ""
            return [f"Le modèle n’a pas assez d’observations exploitables{rows_text} ; "
                    "aucune estimation n’est produite."]
        if item.get("price_stale"):
            return [f"Dernier cours daté de {item.get('price_age_days')} jours (maximum "
                    f"{item.get('max_price_age_days', STALE_PRICE_DAYS)}) : le signal est "
                    "bloqué par prudence tant que le cours n’est pas à jour."]
        if coverage is not None and coverage < c_min:
            return [f"Indice de couverture des données {fr_percent(coverage, 0)} inférieur "
                    f"au minimum requis de {fr_percent(c_min, 0)} : le signal est bloqué "
                    "par prudence."]
        return ["Éléments insuffisants pour qualifier un signal."]

    reasons = []
    if status == "BUY_OPPORTUNITY_REVIEW":
        reasons.append(f"Score {fr_score(score)} ≥ seuil d’examen {fr_score(s_thr)}.")
        reasons.append(f"Probabilité estimée {fr_percent(prob)} ≥ seuil "
                       f"{fr_percent(p_thr)}.")
        reasons.append(f"Couverture des données {fr_percent(coverage, 0)} ≥ minimum "
                       f"{fr_percent(c_min, 0)}.")
    elif status == "WATCH":
        reasons.append(f"Score {fr_score(score)} ≥ seuil de surveillance "
                       f"{fr_score(WATCH_SCORE_THRESHOLD)}.")
        if score is not None and score < s_thr:
            reasons.append(f"Score inférieur au seuil d’examen {fr_score(s_thr)}.")
        if prob is not None and prob < p_thr:
            reasons.append(f"Probabilité estimée {fr_percent(prob)} inférieure au seuil "
                           f"{fr_percent(p_thr)}.")
    elif status == "REGULAR_DCA":
        reasons.append(f"Score {fr_score(score)} inférieur au seuil de surveillance "
                       f"{fr_score(WATCH_SCORE_THRESHOLD)} : aucun signal particulier.")
    return reasons


# ---------------------------------------------------------------- model quality
def model_quality(item: dict) -> dict | None:
    """Describe the hold-out validation honestly; None if no model estimate."""
    validation = item.get("validation") or {}
    brier, ref = _num(validation.get("brier")), _num(validation.get("brier_reference"))
    auc = _num(validation.get("auc"))
    if brier is None:
        return None
    parts = [f"Brier {fr_number(brier, 3)}"]
    if ref is not None:
        parts.append(f"référence {fr_number(ref, 3)}")
    if auc is not None:
        parts.append(f"AUC {fr_number(auc, 2)}")
    if ref is None:
        verdict, tone = "Pas de référence disponible pour juger le modèle.", "neutral"
    elif brier < ref:
        verdict, tone = ("Sur la période de test, le modèle a fait mieux que la simple "
                         "fréquence historique. Résultat préliminaire (un seul test)."), "info"
    else:
        verdict, tone = ("Sur la période de test, le modèle n’a pas fait mieux que la "
                         "simple fréquence historique : la probabilité affichée n’apporte "
                         "pas d’information démontrée."), "warning"
    period = ""
    if validation.get("test_start") and validation.get("test_end"):
        period = (f"Test du {fr_date(validation['test_start'])} au "
                  f"{fr_date(validation['test_end'])}, "
                  f"{validation.get('test_rows', '?')} séances.")
    return {"summary": " · ".join(parts), "verdict": verdict, "tone": tone, "period": period}


# ---------------------------------------------------------------- ETF card
def price_age_days(item: dict, run_date) -> int | None:
    as_of, run = parse_day(item.get("as_of")), parse_day(run_date)
    if not as_of or not run:
        return None
    return (run - as_of).days


def build_etf_card(item: dict, th: dict, run_date) -> dict:
    status = status_of(item)
    horizon = int(item.get("horizon_days") or th["horizon_days"])
    currency = item.get("currency")
    has_estimate = item.get("prob_positive") is not None
    name = str(item.get("name") or item.get("id") or "ETF")
    symbol = str(item.get("symbol") or item.get("id") or "").upper()

    observed = []
    if item.get("price") is not None:
        age = price_age_days(item, run_date)
        note = f"Clôture du {fr_date(item.get('as_of'))}" if item.get("as_of") else \
            "Date de cotation inconnue"
        if age is not None and age > int(item.get("max_price_age_days") or STALE_PRICE_DAYS):
            note += f" · cours ancien de {age} jours"
        value = fr_number(item.get("price"), 2) + (f"{NBSP}{currency}" if currency else "")
        observed.append({"label": "Dernier cours", "value": value, "note": note})
    if item.get("drawdown") is not None:
        observed.append({"label": "Recul depuis le plus haut",
                         "value": fr_percent(item.get("drawdown"), 1),
                         "note": "Historique chargé, 10 ans max."
                                 + (f" Calcul en {currency}." if currency else "")})
    if item.get("rsi14") is not None:
        observed.append({"label": "RSI 14 jours", "value": fr_number(item.get("rsi14"), 0),
                         "note": "Sous 30 : survente ; au-dessus de 70 : surachat"})

    estimated = []
    if has_estimate:
        base = item.get("base_rate_positive")
        estimated.append({
            "label": f"Probabilité de rendement positif à {horizon} séances",
            "value": fr_percent(item.get("prob_positive"), 0),
            "note": (f"Fréquence historique observée : {fr_percent(base, 0)}"
                     if base is not None else "Fréquence historique non disponible"),
        })
        estimated.append({
            "label": f"Rendement estimé à {horizon} séances",
            "value": fr_percent(item.get("expected_return"), 1, signed=True),
            "note": "Estimation ponctuelle, non validée hors échantillon",
        })

    quality = []
    if item.get("data_coverage") is not None:
        quality.append(f"Indice de couverture des données : {fr_percent(item['data_coverage'], 0)}"
                       f" (indice interne pondéré, minimum {fr_percent(th['min_coverage'], 0)}).")
    if "valuation_coverage_weight" in item:
        upside = item.get("valuation_weighted_upside")
        text = ("Valorisation des constituants US/Canada : "
                f"{fr_percent(item.get('valuation_coverage_weight'), 0)} du poids total de l’ETF couvert")
        if upside is not None:
            text += (f" ; potentiel pondéré de la partie couverte {fr_percent(upside, 1, True)}"
                     " (indicateur partiel, pas une juste valeur de l’ETF).")
        else:
            text += " ; aucune valorisation disponible."
        quality.append(text)
    if "holdings_file_weight" in item:
        file_weight = item.get("holdings_file_weight") or 0.0
        if file_weight <= 0:
            quality.append("Aucun fichier de constituants exploitable : valorisation et "
                           "consensus non calculés.")
        else:
            text = (f"Fichier de constituants : {fr_percent(file_weight, 0)} du poids de l’ETF")
            if item.get("holdings_as_of"):
                text += f", au {fr_date(item['holdings_as_of'])}"
            else:
                text += ", date non renseignée"
            if item.get("holdings_source"):
                text += f" (source : {item['holdings_source']})"
            quality.append(text + ".")
    if item.get("valuation_implausible_count"):
        quality.append(f"{item['valuation_implausible_count']} valorisation(s) implausible(s) "
                       "exclue(s) ; unité de l’API à vérifier.")
    analyst = item.get("analyst") or {}
    if analyst.get("analyst_coverage_weight") is not None:
        quality.append("Consensus d’analystes : "
                       f"{fr_percent(analyst.get('analyst_coverage_weight'), 0)} du poids couvert.")
    if item.get("rows") is not None:
        quality.append(f"Observations utilisées par le modèle : {item['rows']}.")

    if status == "BUY_OPPORTUNITY_REVIEW":
        headline = ("Les seuils de recherche sont franchis : cela justifie une analyse "
                    "complémentaire, pas un achat automatique.")
    elif status == "WATCH":
        headline = "Situation à suivre ; les seuils d’examen ne sont pas tous atteints."
    elif status == "REGULAR_DCA":
        headline = "Pas de signal particulier ; le plan DCA habituel reste la référence."
    else:
        headline = "Pas de lecture possible aujourd’hui faute de données suffisantes."

    return {
        "id": item.get("id"),
        "name": name,
        "symbol": symbol,
        "isin": item.get("isin"),
        "status": status,
        "status_label": status_label(status),
        "tone": SIGNAL_TONES.get(status, "neutral"),
        "score": fr_score(item.get("score")) if item.get("score") is not None else MISSING,
        "headline": headline,
        "horizon_days": horizon,
        "observed": observed,
        "estimated": estimated,
        "model_quality": model_quality(item) if has_estimate else None,
        "reasons": signal_reasons(item, th),
        "quality": quality,
    }


# ---------------------------------------------------------------- macro
def _period_start(value, frequency):
    text = str(value or "").strip()
    try:
        if frequency == "Q" and "-Q" in text:
            year, quarter = text.split("-Q", 1)
            return date(int(year), 3 * int(quarter) - 2, 1)
        if frequency == "M":
            year, month = text[:7].split("-")
            return date(int(year), int(month), 1)
    except (ValueError, IndexError):
        return None
    return parse_day(text)


def macro_is_old(period, frequency, run_date) -> bool:
    start, run = _period_start(period, frequency), parse_day(run_date)
    if not start or not run:
        return False
    return (run - start).days > MACRO_MAX_AGE_DAYS.get(frequency, 10)


def build_macro(macro_snapshot: dict | None, run_date=None) -> dict:
    snapshot = macro_snapshot or {}
    groups, missing, old = {}, [], []
    for key, label, unit, region, decimals, frequency in MACRO_DIGEST_FIELDS:
        value = snapshot.get(key)
        if _num(value) is None:
            missing.append(f"{label} ({region})")
            continue
        shown = fr_points(value, decimals) if unit == "%" else fr_number(value, decimals)
        is_old = macro_is_old(snapshot.get(key + "_date"), frequency, run_date)
        if is_old:
            old.append(f"{label} ({region})")
        groups.setdefault(region, []).append({
            "label": label,
            "value": shown,
            "period": fr_period(snapshot.get(key + "_date"), frequency)
                      + (" · observation ancienne" if is_old else ""),
        })
    available = sum(len(rows) for rows in groups.values())
    return {
        "groups": [{"region": region, "rows": rows} for region, rows in groups.items()],
        "available": available,
        "total": len(MACRO_DIGEST_FIELDS),
        "missing": missing,
        "old": old,
    }


def format_macro_digest(macro_snapshot: dict | None, run_date=None) -> list[str]:
    """Plain-text macro block (kept for backward compatibility)."""
    macro = build_macro(macro_snapshot, run_date)
    if not macro["available"]:
        return [f"Aucune observation macroéconomique disponible pour ce cycle "
                f"({macro['total']} séries interrogées)."]
    lines = []
    for group in macro["groups"]:
        lines.append(group["region"].upper())
        for row in group["rows"]:
            lines.append(f"- {row['label']} : {row['value']} (période : {row['period']})")
    lines.append(f"{macro['available']}/{macro['total']} séries disponibles.")
    if macro["missing"]:
        lines.append("Indisponibles ce jour : " + ", ".join(macro["missing"]) + ".")
    return lines


# ---------------------------------------------------------------- data status
def build_data_status(results: list[dict], macro: dict, run_date) -> dict:
    reasons = []
    analysed = [r for r in results if r.get("prob_positive") is not None]
    if results:
        reasons.append(f"{len(analysed)}/{len(results)} ETF disposent d’une estimation du modèle.")
    stale = [str(r.get("symbol") or r.get("id")).upper() for r in results
             if r.get("price_stale") or (price_age_days(r, run_date) or 0)
             > int(r.get("max_price_age_days") or STALE_PRICE_DAYS)]
    if stale:
        reasons.append("Cours anciens : " + ", ".join(stale) + ".")
    reasons.append(f"{macro['available']}/{macro['total']} séries macroéconomiques disponibles.")
    if analysed and all(not r.get("valuation_coverage_weight") for r in analysed):
        reasons.append("Aucune valorisation fondamentale des constituants disponible.")

    if not results or not analysed or macro["available"] < macro["total"] / 2:
        level, label = "degraded", "Données dégradées"
    elif stale or len(analysed) < len(results) or macro["missing"] or \
            any(not r.get("valuation_coverage_weight") for r in analysed):
        level, label = "partial", "Données partielles"
    else:
        level, label = "complete", "Données complètes"
    return {"level": level, "label": label, "reasons": reasons}


# ---------------------------------------------------------------- public builders
def _counts(results: list[dict]) -> dict:
    counts = {key: 0 for key in STATUS_ORDER}
    for item in results:
        status = status_of(item)
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_digest_view(results: list[dict], run_date, macro_snapshot: dict | None = None,
                      strategy: dict | None = None, retrieved_at: str | None = None) -> dict:
    results = list(results or [])
    th = thresholds_from_strategy(strategy)
    counts = _counts(results)
    macro = build_macro(macro_snapshot, run_date)
    status = build_data_status(results, macro, run_date)
    cards = [build_etf_card(item, th, run_date) for item in results]
    cards.sort(key=lambda c: STATUS_ORDER.index(c["status"])
               if c["status"] in STATUS_ORDER else len(STATUS_ORDER))

    review, watch = counts["BUY_OPPORTUNITY_REVIEW"], counts["WATCH"]
    limited = counts["INSUFFICIENT_EVIDENCE"] + counts["INSUFFICIENT_PRICE_HISTORY"]
    if review:
        headline = (f"{review} ETF franchi{'ssent' if review > 1 else 't'} les seuils "
                    "d’examen aujourd’hui. C’est une invitation à approfondir, pas un "
                    "signal d’achat.")
    elif watch:
        headline = (f"{watch} ETF {'méritent' if watch > 1 else 'mérite'} une "
                    "surveillance. Aucun ne franchit les seuils d’examen.")
    elif results and limited == len(results):
        headline = "Aucune lecture possible aujourd’hui : les données sont insuffisantes."
    else:
        headline = ("Aucun signal particulier aujourd’hui. Le plan DCA habituel reste "
                    "le scénario de référence.")

    bullets = [f"{c['symbol']} : {c['status_label'].lower()} (score {c['score']})"
               for c in cards if c["status"] in ("BUY_OPPORTUNITY_REVIEW", "WATCH")]
    bullets.append(f"Les probabilités portent sur un horizon de {th['horizon_days']} "
                   "séances et restent des estimations incertaines.")

    day = fr_date(run_date)
    parts = []
    if review:
        parts.append(f"{review} à examiner")
    if watch:
        parts.append(f"{watch} à surveiller")
    if not parts:
        parts.append("aucun signal particulier")
    subject = f"ETF Wealth Builder · {day} · " + " · ".join(parts) + f" · {status['label']}"

    return {
        "kind": "digest",
        "subject": subject,
        "title": "Rapport quotidien",
        "subtitle": f"Recherche et aide à la décision · {day}"
                    + (f" · données récupérées à {str(retrieved_at)[11:16]} UTC"
                       if retrieved_at and len(str(retrieved_at)) >= 16 else ""),
        "date_label": day,
        "preheader": headline,
        "summary": {
            "headline": headline,
            "bullets": bullets,
            "counts": [
                {"label": "À examiner", "value": review, "tone": "positive"},
                {"label": "À surveiller", "value": watch, "tone": "warning"},
                {"label": "DCA habituel", "value": counts["REGULAR_DCA"], "tone": "info"},
                {"label": "Données limitées", "value": limited, "tone": "neutral"},
            ],
        },
        "data_status": status,
        "overview": [{"name": c["name"], "symbol": c["symbol"], "status_label": c["status_label"],
                      "tone": c["tone"], "score": c["score"]} for c in cards],
        "etfs": cards,
        "macro": macro,
        "methodology": METHODOLOGY_NOTES,
        "disclaimer": DISCLAIMER,
        "thresholds": th,
    }


def build_alert_view(result: dict, horizon_days: int | None = None,
                     strategy: dict | None = None, run_date=None) -> dict:
    th = thresholds_from_strategy(strategy)
    if horizon_days:
        th["horizon_days"] = int(horizon_days)
    item = dict(result)
    item.setdefault("horizon_days", th["horizon_days"])
    run_date = run_date or item.get("as_of") or date.today().isoformat()
    card = build_etf_card(item, th, run_date)
    headline = (f"{card['name']} franchit les seuils d’examen du modèle. Il s’agit d’une "
                "invitation à vérifier les données et le contexte, jamais d’un ordre d’achat.")
    return {
        "kind": "alert",
        "subject": f"ETF Wealth Builder · Signal à examiner · {card['symbol']} · "
                   f"{fr_date(item.get('as_of') or run_date)}",
        "title": f"Signal à examiner · {card['symbol']}",
        "subtitle": f"Alerte de recherche · horizon {th['horizon_days']} séances",
        "date_label": fr_date(item.get("as_of") or run_date),
        "preheader": headline,
        "summary": {"headline": headline, "bullets": [], "counts": []},
        "data_status": None,
        "overview": [],
        "etfs": [card],
        "macro": None,
        "methodology": METHODOLOGY_NOTES,
        "disclaimer": DISCLAIMER,
        "thresholds": th,
    }

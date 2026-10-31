# Lot 1 — E-mail et sûreté d'exécution

Branche : `claude/project-thread-mw0vfh` · Référence : `docs/audit/2026-10-31-audit-phase1.md` (constats C2, C4, E6, M1, M2, M3, M7, F2)

Ce document est écrit pour être relu par un second assistant (ChatGPT) et par JG.

## Objectif

Rendre les e-mails lisibles comme ceux d'une plateforme de recherche, sans changer **aucun** signal, seuil ni paramètre de stratégie. Sécuriser l'envoi pour qu'une panne d'e-mail ne fasse jamais perdre les résultats du jour.

## Fichiers modifiés

| Fichier | Nature | Raison |
|---|---|---|
| `src/notifications/transport.py` | nouveau | SMTP avec TLS vérifié (STARTTLS 587, TLS implicite 465), en-têtes `Date` et `Message-ID`, mode `EMAIL_DRY_RUN` (écriture `.eml`), erreurs journalisées (type seulement), jamais d'exception |
| `src/notifications/formatting.py` | nouveau | Format FR/BE (« 2,00 % », « 30/10/2026 », « sept. 2026 », « T2 2026 »), arrondi au demi supérieur, valeur manquante affichée « — » |
| `src/notifications/view_model.py` | nouveau | Contenu unique pour HTML et texte : synthèse, statut de qualité des données, fiches ETF en trois blocs (observé, estimé, lecture de recherche), motifs du statut, qualité de validation, macro avec période et séries indisponibles |
| `src/notifications/render.py` | nouveau | Gabarit HTML 600 px (ghost table Outlook, media query mobile, textes ≥ 12 px) et rendu texte |
| `src/notifications/preview.py` | nouveau | `python -m src.notifications.preview` : 5 scénarios fictifs en HTML + TXT, aucun envoi |
| `src/notifications/email_alert.py` | réécrit (façade) | Mêmes fonctions publiques `send_digest`, `send_signal_alert`, `format_macro_digest` ; ajout `compose_*` sans envoi |
| `src/main.py` | modifié | Rapport JSON écrit **avant** les notifications ; alertes envoyées après la boucle ; chaque notification isolée ; identité (ISIN, symbole, devise, horizon) jointe à tous les résultats ; date de cours sans heure ; NaN → `None` pour drawdown/RSI |
| `src/models/probabilistic.py` | ajout de métriques | `base_rate_positive`, `validation.brier_reference`, période et taille du test. **Affichage uniquement** : aucune décision n'utilise ces valeurs |
| `src/strategy/opportunity.py` | constante | `WATCH_SCORE_THRESHOLD = 55` nommée pour l'expliquer dans l'e-mail ; valeur inchangée |
| `tests/conftest.py` | nouveau | Supprime les secrets de l'environnement, force le dry-run et fait échouer toute ouverture SMTP réelle |
| `tests/test_macro_email_digest.py` | réécrit | Nouveaux formats ; assertion tautologique supprimée ; 14 tests |
| `tests/test_email_transport.py`, `tests/test_formatting_and_preview.py`, `tests/test_main_pipeline.py` | nouveaux | Transport, formats, aperçus, cycle complet avec fournisseurs simulés |
| `.github/workflows/tests.yml` | modifié | Génère et publie les aperçus e-mail en artefact (14 jours) |
| `.gitignore`, `README.md`, `docs/MODEL_GOVERNANCE.md` | mineur | `data/previews/`, `data/outbox/` ignorés ; doc du dry-run ; `\n` littéral corrigé |

Aucun fichier supprimé.

## Choix techniques

1. **Un modèle de vue unique** (`view_model.py`) : HTML et texte ne peuvent plus diverger.
2. **Séparation sémantique** : *Observé* (cours, recul, RSI), *Estimé* (probabilité et rendement du modèle, toujours avec horizon, fréquence historique et verdict de validation), *Lecture de recherche* (statut + règles franchies ou non).
3. **Verdict de validation honnête** : si le Brier du modèle n'est pas inférieur à celui de la fréquence historique sur la période de test, l'e-mail écrit que la probabilité « n'apporte pas d'information démontrée ». Cela n'agit pas sur le signal (décision humaine requise, lot 4).
4. **Données manquantes** : jamais remplacées. Les séries macro absentes sont listées en une ligne ; si tout manque, un seul message.
5. **Compatibilité** : pas de grille multi-colonnes dans les fiches (lignes libellé/valeur), donc rien à empiler sur mobile ; Outlook reçoit une largeur fixe via commentaire conditionnel MSO.
6. **Objet informatif** : `ETF Wealth Builder · 30/10/2026 · 1 à examiner · 1 à surveiller · Données partielles`.

## Hypothèses

- L'horizon est exprimé en **séances** (le label est un décalage de 63 lignes de cotation), pas en jours calendaires.
- Un cours est signalé « ancien » au-delà de 4 jours calendaires (couvre un week-end + 1 jour férié). Seuil d'affichage uniquement.
- La « fréquence historique » est la proportion de rendements positifs à l'horizon sur toutes les lignes étiquetées de l'historique chargé (10 ans max.).
- Le statut global (complètes / partielles / dégradées) est une règle d'affichage simple, documentée dans `build_data_status`.

## Limites connues (traitées dans les lots suivants)

- Pas encore de « ce qui a changé depuis hier » : nécessite l'état persistant (lot 3).
- La couverture fondamentale reste calculée sur des poids renormalisés (constat C3, lot 2).
- Le CPI US reste affiché en niveau d'indice (étiqueté comme tel) ; passage en glissement annuel au lot 2.
- Rendu vérifié dans Chromium (800 et 375 px), **pas dans de vrais clients** Gmail, Outlook, Apple Mail. À contrôler par JG avec les aperçus ou un envoi dry-run.
- Les alertes immédiates ne sont pas dédupliquées (lot 3).

## Tests effectués

- `python -m compileall -q src tests` : OK.
- `pytest` : **39 tests passent** (12 avant). Aucun e-mail réel possible (SMTP bloqué par `conftest.py`).
- Génération des 5 aperçus et captures Chromium desktop et mobile.

## Décisions nécessitant une validation humaine

1. Le libellé et le ton des e-mails (français de Belgique, vouvoiement implicite).
2. Faut-il garder l'e-mail d'alerte séparé en plus du digest ?
3. Le verdict de validation est affiché mais ne bloque pas les signaux : le blocage relève du lot 4.

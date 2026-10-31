# ETF Wealth Builder — Rapport d'audit, phase 1

Date : 31 octobre 2026 · Commit audité : `3b01901` (master) · Auteur : Claude (audit indépendant, aucune modification de code)

## 0. Synthèse exécutive

Le dépôt est un **squelette de recherche propre et prudent dans son discours**, avec de bonnes pratiques de sécurité sur les clés API, un filtrage US/Canada correct pour ValueInvesting.io et des dates d'observation macro conservées. En revanche, **le fonctionnement réel est en retrait par rapport à ce que la documentation et les e-mails laissent entendre** :

1. **Les probabilités ML ne sont pas validées avant d'être affichées ni utilisées pour alerter.** Sur 8 marches aléatoires simulées (aucune prévisibilité possible), le modèle produit des probabilités de 33 % à 82 % et des AUC de holdout de 0,33 à 0,87. Le seuil d'alerte de 0,62 est proche de la fréquence historique de rendements positifs à 63 jours d'un ETF actions ; il est donc franchi sans que le modèle ait démontré une capacité prédictive.
2. **La connexion SMTP n'authentifie pas le serveur** (STARTTLS sans vérification de certificat) : le mot de passe SMTP peut être intercepté par un intermédiaire.
3. **La couverture fondamentale peut être fortement surestimée** : les poids des fichiers de constituants sont renormalisés à 100 %, ce qui viole la contrainte « couverture exprimée par rapport au poids total de l'ETF » dès qu'un fichier partiel (ex. top 100 lignes) est fourni.
4. **Une panne SMTP fait échouer tout le cycle** : l'alerte immédiate est envoyée avant l'écriture du rapport, sans gestion d'erreur.
5. **L'e-mail est visuellement soigné mais sémantiquement insuffisant** : probabilité et rendement sans horizon, prix sans devise ni date, pas de référence (fréquence de base), pas de motif du signal, observations, estimations et lecture de recherche mélangées sur une même ligne.

Aucune de ces corrections ne nécessite une réécriture. Je propose 6 lots incrémentaux (section 5), en commençant par l'e-mail et la sûreté d'exécution, sans toucher aux seuils de décision.

## 1. Méthode

- Lecture intégrale des 38 fichiers suivis (≈1 860 lignes : `src/`, `tests/`, `config/`, workflows, docs).
- `python -m compileall src tests` : OK. `pytest` : **12/12 tests passent** (Python 3.13 ; `ta` exclu car il ne compile pas sur 3.13, et il n'est importé nulle part).
- Génération locale d'aperçus HTML du digest et de l'alerte (données fictives), captures Chromium à 800 px et 375 px.
- Simulation du modèle (`fit_predict`) sur 8 marches aléatoires géométriques de 10 ans (drift 7 %/an, vol 16 %).
- **Limites de l'audit** : les appels réseau vers Yahoo, ECB, Eurostat, FRED, Finnhub et ValueInvesting.io sont bloqués depuis mon environnement ; les adaptateurs n'ont donc pas été vérifiés en conditions réelles. Le rendu e-mail n'a été vérifié que dans Chromium, pas dans de vrais clients Gmail, Outlook ou Apple Mail. Aucun secret n'a été lu, aucun e-mail réel envoyé.

## 2. Ce qui fonctionne bien (à préserver)

- Les clés API ne sont jamais journalisées (seul `type(exc).__name__` est loggé pour les fournisseurs qui mettent la clé dans l'URL).
- `eligible_holdings_for_valueinvesting` exige un champ `market` explicite et n'envoie que US/CA ; testé.
- `weighted_constituent_upside` calcule la couverture sur le poids total des lignes et sépare marché supporté / valorisé ; testé.
- Les séries macro conservent leur date d'observation ; les valeurs manquantes restent `None` (pas d'imputation).
- Les avertissements (« pas un conseil », « pas une garantie », « pas la juste valeur de l'ETF ») sont présents.
- Workflow : `permissions: contents: read`, secrets passés uniquement à l'étape de monitoring, tests exécutés avant.
- `docs/MODEL_GOVERNANCE.md` décrit honnêtement les limites (pas de purge, pas d'embargo, pas de vintages).

## 3. Diagnostic classé par gravité

Légende : **Critique** = peut induire une décision erronée ou exposer un secret ; **Élevé** = fonctionnalité trompeuse ou fragile ; **Moyen** = qualité, robustesse, maintenabilité ; **Faible** = finition.

### Critique

**C1. Probabilités et alertes non conditionnées à la validation du modèle** — `src/models/probabilistic.py`, `src/main.py:79-153`
- Un seul holdout chronologique (75/25) ; Brier et AUC sont calculés puis ignorés. La règle de `MODEL_GOVERNANCE.md` « Never alert BUY if model validation fails » n'est pas implémentée.
- Aucune comparaison à la fréquence de base (taux historique de rendements positifs à 63 j) ni à une régression logistique.
- Simulation sur marches aléatoires (aucun signal réel) :

| Graine | Fréq. de base | Proba prédite | Rend. estimé | AUC holdout |
|---|---|---|---|---|
| 0 | 0,50 | 0,36 | +7,8 % | 0,42 |
| 1 | 0,51 | 0,62 | −3,8 % | 0,44 |
| 5 | 0,65 | 0,50 | −7,3 % | **0,87** |
| 6 | 0,62 | **0,82** | +5,5 % | 0,33 |

  Un AUC de 0,87 sur du bruit montre que le holdout unique (~550 lignes dont les labels se chevauchent sur 63 jours, soit ~9 périodes indépendantes) ne permet pas de conclure. La graine 6 franchirait le seuil de probabilité 0,62 avec un AUC de 0,33.
- Le régresseur de rendement est entraîné sur le seul jeu d'entraînement, n'est jamais évalué, et son résultat est affiché comme « Rendement estimé ».
- **Impact** : l'e-mail présente une estimation non validée avec la même présentation que des observations.

**C2. SMTP STARTTLS sans vérification du certificat** — `src/notifications/email_alert.py:67`
- `server.starttls()` sans `context` utilise `ssl._create_stdlib_context()` (vérifié : `verify_mode=CERT_NONE`, `check_hostname=False`). Le serveur n'est pas authentifié avant `login()`.
- Correctif : `starttls(context=ssl.create_default_context())`, plus support `SMTP_SSL` pour le port 465.

**C3. Couverture fondamentale surestimée par la renormalisation des poids** — `src/main.py:33-39`
- `load_holdings` divise chaque poids par la somme du fichier. Si le fichier contient les 200 premières lignes de VWCE (~45 % du fonds), la couverture affichée est rapportée à 45 % et non à 100 %. Contrainte §4 violée.
- L'heuristique `total > 1.5 ⇒ pourcentages` est fragile.
- La composante valorisation pèse 20 % du score quelle que soit la couverture (2 % de couverture ⇒ même poids qu'à 60 %).
- L'unité de `upside_dcf_ebitda_10` (fraction ou pourcentage) n'est vérifiée nulle part : si l'API renvoie 25 pour 25 %, `clamp01(0.5 + 25)` sature à 1.

**C4. Une erreur SMTP interrompt tout le cycle** — `src/main.py:151-163`, `email_alert.py:66-70`
- `send_signal_alert` est appelé dans la boucle, avant `write_report` ; aucune exception n'est interceptée. Un serveur SMTP indisponible ⇒ pas de rapport JSON, pas de digest, ETF suivants non analysés.

### Élevé

**E1. Aucune déduplication des alertes** — `config/strategy.yaml` (`max_alerts_per_etf_per_day`, `email_on_signal_upgrade_only`) n'est lu nulle part ; le cache `data/state` du workflow est restauré mais rien n'y est écrit. Un signal qui persiste 10 jours produit 10 alertes + 10 digests.

**E2. Score de couverture des données gonflé par des flux génériques** — `src/main.py:112-127`, `src/features/news.py`
- `news_coverage = 1.0` dès qu'un titre d'actualité générale existe ; le même sentiment VADER (outil peu adapté aux titres financiers) est appliqué à tous les ETF (S&P 500 comme marchés émergents).
- Scénario réaliste : clé Finnhub + macro complète, **aucun fichier de constituants** ⇒ couverture = 0,45 + 0,15 + 0,15 = 0,75 ≥ 0,70 ⇒ un `BUY_OPPORTUNITY_REVIEW` peut être émis sans aucune donnée fondamentale.
- Le composant s'appelle `macro_news` mais **aucune donnée macro n'entre dans le score** ; la macro ne sert qu'à l'affichage et à la couverture.
- Les composantes manquantes sont exclues et les poids renormalisés : moins de preuves peut donner un score plus élevé.

**E3. Biais temporels et configuration trompeuse** — `src/models/probabilistic.py`
- Pas de purge ni d'embargo à la frontière train/test et dans les plis de calibration alors que les labels se chevauchent sur 63 jours.
- Paramètres de config **non utilisés** : `walk_forward_test_fraction`, `minimum_validation_rows`, `forecast_horizons_days`, `random_state`, `score_weights` (dupliqués en dur dans `opportunity.py`), tout `risk_management.yaml`. Modifier la config n'a aucun effet, ce qui est trompeur.
- `suggested_tranche` (DCA modifié) et `monthly_dca` (benchmark) ne sont jamais appelés : la stratégie Modified DCA n'est pas encore opérationnelle.

**E4. Constituants absents et appels Finnhub non bornés**
- Aucun des fichiers `data/constituents/*_constituents.csv` référencés n'existe : en production, valorisation et consensus analystes sont toujours vides.
- `aggregate_recommendations` appelle Finnhub une fois par ligne (VWCE ≈ 3 700 lignes, quota gratuit 60/min) y compris pour des tickers non US ; pas de rate limiting ni de cache ; `rows[0]` sans contrôle de fraîcheur.

**E5. Devise, frais et fiscalité absents**
- `CSPX.L` et `EIMI.L` sont des lignes en USD pour un investisseur en EUR : rendements, drawdown et prix sont en USD sans conversion. Les prix e-mail n'affichent pas de devise.
- Aucune prise en compte des frais (TER, courtage), spreads, change, TOB, précompte ou taxe belge sur les plus-values (2026). Exigence §4 non couverte.

**E6. E-mail : sens des chiffres insuffisant** (détail section 4)
- Digest : « Probabilité positive » et « Rendement estimé » **sans horizon** ; prix sans devise ni date ; aucune fréquence de base ; aucun motif du signal ; « Couverture des données » est un indice heuristique présenté comme un pourcentage factuel.

### Moyen

**M1. Compatibilité clients mail** — pas de « ghost table » MSO : Outlook Windows ignore `max-width` et étire le contenu ; pas de media queries : sur mobile (375 px) la ligne de 6 indicateurs se comprime (libellés sur 3 lignes) ; polices de 10–11 px sous le seuil de lisibilité mobile ; `border-radius` et le `padding` des badges ignorés par Outlook ; préheader sans remplissage (Gmail affiche le texte suivant).

**M2. Formatage et exactitude du contenu**
- Format anglo-saxon (« 2.00% ») au lieu du format FR/BE (« 2,00 % ») ; score 62,5 affiché « 62 » (arrondi bancaire) ; date de cours « 2026-10-30 00:00:00 » ; EUR/USD à 2 décimales ; CPI US affiché en niveau d'indice (324,10) au lieu d'une variation annuelle.
- Version texte : « ZONE EURO » apparaît deux fois (ordre des champs entrelacé).
- La mention « séries sans nouvelle observation volontairement masquées » est inexacte : ce sont des séries indisponibles, et elles ne sont pas listées. Un rapport professionnel doit dire ce qui manque.

**M3. Transport e-mail** — pas d'en-têtes `Date` ni `Message-ID` (spam score, tri) ; `send_email` renvoie `False` silencieusement sans log ; pas de mode dry-run ni de génération d'aperçus ; l'objet ne résume pas le contenu.

**M4. Fraîcheur des données** — aucun contrôle de l'âge du dernier cours ni des observations macro ; pas d'horodatage de récupération ; FRED télécharge depuis 2000 pour une seule valeur ; pas de dates de publication (ALFRED).

**M5. Architecture** — la logique métier (score technique, formule de couverture, mélange news/analystes) est dans `main.run_once`, non testée ; données en dictionnaires libres ; pas de point d'injection pour tester le pipeline ; `NaN` possibles dans le JSON ; le « rapport HTML » n'existe que sous forme d'e-mail (`report.py` n'écrit que du JSON).

**M6. Dépendances** — versions non épinglées (`>=`), `yfinance` est fragile ; `ta` et `joblib` inutilisés (et `ta` ne compile pas sous Python 3.13) ; `pytest` dans les dépendances de production.

**M7. Tests** — 12 tests ; aucun sur `run_once`, `load_holdings`, `fit_predict`, `send_email`, les modes d'échec ; une assertion tautologique (`tests/test_macro_email_digest.py:84`, toujours vraie) ; pas de test de non-régression visuelle.

### Faible

- F1. Actions GitHub épinglées par tag et non par SHA ; tests exécutés deux fois (workflow tests + monitor).
- F2. `docs/MODEL_GOVERNANCE.md:18` contient un `\n` littéral.
- F3. Cartes « Historique insuffisant » affichent l'identifiant brut (« iwda ») et une rangée de tirets sans explication.
- F4. Valeurs codées en dur (220 lignes minimum, seuil WATCH 55, `random_state=42`) ; import `datetime` dans la fonction.
- F5. Cron UTC fixe (décalage heure d'été) ; exécution aussi les jours fériés boursiers.

## 4. Évaluation de l'expérience e-mail

### Constat

| Critère | Note | Commentaire |
|---|---|---|
| Esthétique | Bon | Palette sobre, cartes claires, en-tête soigné. |
| Synthèse exécutive | Moyen | Une phrase et 4 compteurs ; ne dit ni ce qui a changé depuis hier ni si les données sont fiables. |
| Hiérarchie | Moyen | 6 indicateurs au même niveau ; le statut est un petit badge. |
| Sens des chiffres | Insuffisant | Pas d'horizon, de devise, de date, de référence ni de motif. |
| Observations / estimations / lecture | Absent | Prix observé et probabilité ML côte à côte avec le même style. |
| Qualité des données | Faible | Indice de couverture opaque ; séries manquantes non listées. |
| Gmail / Apple Mail | Correct | Styles inline, tables : bon socle. |
| Outlook Windows | Fragile | Pas de ghost table, pas de largeur fixe. |
| Mobile | Moyen | Fluide mais pas adaptatif ; 6 colonnes trop serrées. |
| Version texte | Bon | Présente et lisible ; mêmes lacunes de sens. |
| Vérification visuelle | Absente | Aucun outil d'aperçu. |

### Structure cible du digest

1. **Objet** informatif : `ETF Wealth Builder · 31/10 · 1 à examiner · 1 à surveiller · Données : partielles`.
2. **Synthèse exécutive** (3 puces max) : ce qui a changé depuis le dernier envoi ; signaux du jour ; état global des données (complètes / partielles / dégradées) avec la raison.
3. **Tableau récapitulatif** : ETF · statut · évolution du statut · score · qualité des données.
4. **Fiche ETF en trois blocs distincts** :
   - *Observé* : cours + devise + date de cotation, drawdown, RSI.
   - *Estimé (modèle statistique)* : « Probabilité de rendement positif à 63 jours de bourse : 64 % (fréquence historique : 68 %) », qualité de validation, avec le libellé « estimation non garantie ».
   - *Lecture de recherche* : statut et **motifs** en langage clair (« score 78 ≥ seuil 75 ; probabilité 0,71 ≥ 0,62 ; valorisation non disponible »), et ce qui manque.
5. **Contexte macro** avec date d'observation, indicateur de fraîcheur, liste explicite des séries indisponibles.
6. **Qualité des données et méthode** : couverture fondamentale sur le poids total de l'ETF, sources, heure de récupération, limites.
7. **Pied de page** : avertissements actuels conservés.

### Exigences techniques

- Gabarit mono-colonne 600 px, ghost tables MSO pour Outlook, media queries pour empiler les indicateurs sous 480 px, corps ≥ 14 px, contraste AA.
- Un **modèle de vue unique** alimente HTML et texte pour qu'ils ne divergent jamais.
- En-têtes `Date`, `Message-ID` ; TLS vérifié ; erreurs SMTP journalisées sans interrompre le cycle.
- `EMAIL_DRY_RUN=1` et une commande `python -m src.notifications.preview` qui écrit des aperçus HTML/TXT à partir de jeux de données fictifs (cas nominal, opportunité, données dégradées, tout manquant) dans `data/previews/`, publiés en artefact CI.
- Tests : structure, absence de mots interdits (« acheter », « garanti »), présence de l'horizon et des dates, aucun envoi réel (SMTP simulé).

## 5. Recommandations et plan d'implémentation

| Lot | Contenu | Change le comportement des signaux ? |
|---|---|---|
| **1. E-mail et sûreté** | TLS vérifié, isolement des erreurs SMTP, dry-run, aperçus, modèle de vue, refonte HTML/texte, horizon/devise/dates/fréquence de base/motifs affichés, tests | Non (affichage et transport uniquement) |
| **2. Intégrité des données** | Couverture sur poids réel (fichier + métadonnées as-of/source), contrôle d'unité de l'upside, fraîcheur cours et macro, liste des séries manquantes, CPI en glissement annuel, FRED borné | Oui (corrige C3) |
| **3. État et déduplication** | Fichier d'état des alertes, application de `email_on_signal_upgrade_only` et `max_alerts_per_etf_per_day` déjà configurés | Oui (moins d'alertes) |
| **4. Validation statistique** | Walk-forward purgé + embargo, références (fréquence de base, logistique), Brier skill score, calibration, verrou d'alerte si le modèle ne bat pas la référence | Oui (décision humaine requise) |
| **5. Coûts, change, fiscalité belge** | Paramètres de frais/spread/TOB/plus-values, conversion EUR, benchmark DCA net | Oui |
| **6. Hygiène** | Config réellement lue, dépendances épinglées, suppression justifiée de `ta`/`joblib`, CI | Non |

Chaque lot = une PR sur une branche `claude/…`, jamais sur master.

## 6. Architecture cible (évolution, pas réécriture)

```
src/
  domain/          # dataclasses : Observation(value, unit, period, source, retrieved_at),
                   # EtfAssessment, SignalDecision(status, reasons[])
  data/            # adaptateurs actuels + retrieved_at + contrôles de fraîcheur
  scoring/         # score technique, couverture, mélange news/analystes (sortis de main.py)
  models/
    probabilistic.py
    validation.py  # walk-forward purgé, références, verrou de validation
  state/           # état des alertes, futur registre de trésorerie
  costs/           # frais, spreads, FX, fiscalité belge (lot 5)
  notifications/
    view_model.py  # construit le contenu une seule fois
    render_html.py / render_text.py
    transport.py   # SMTP TLS vérifié, dry-run
    preview.py     # aperçus HTML/TXT
  pipeline.py      # orchestration testable (fournisseurs injectables)
  main.py          # CLI mince
```

## 7. Décisions nécessitant une validation humaine

1. **Valider ce rapport et l'ordre des lots** (je propose de commencer par le lot 1).
2. **Verrou de validation (lot 4)** : faut-il bloquer `BUY_OPPORTUNITY_REVIEW` quand le modèle ne bat pas la fréquence de base hors échantillon ? Ma recommandation : oui (« fail closed »), conforme à `MODEL_GOVERNANCE.md`.
3. **Couverture des données** : la formule (0,45 / 0,15 / 0,10 / 0,15 / 0,15) et le comptage des news génériques sont des paramètres de décision ; je ne les modifierai pas sans accord. Recommandation : ne plus compter les news générales comme couverture spécifique à l'ETF.
4. **Unité de l'upside ValueInvesting.io** : un exemple de réponse (sans clé) permettrait de confirmer fraction vs pourcentage.
5. **Lignes de cotation** : garder CSPX.L/EIMI.L (USD) ou passer à des lignes en EUR (ex. Xetra) ? Choix d'investisseur.
6. **Paramètres fiscaux belges** (TOB par ETF selon son statut, taxe sur les plus-values 2026, précompte) : à confirmer par vous ou un conseiller avant implémentation.
7. **Alerte séparée ou digest seul** : garder un e-mail immédiat par opportunité, ou un seul digest avec un objet marqué ?

## 8. Notes pour la revue croisée (ChatGPT)

- Fichiers modifiés : aucun (phase d'audit).
- Hypothèses : comportement déduit du code ; adaptateurs réseau non testés en réel.
- Tests effectués : compileall, pytest 12/12, simulation Monte Carlo (8 graines) du modèle, rendu Chromium 800/375 px.
- Points à challenger côté quant/actuariat : le nombre effectif d'observations indépendantes avec labels chevauchants ; le choix du Brier skill score face à la fréquence de base comme critère de verrou ; la pertinence de VADER ; la pondération du score composite.

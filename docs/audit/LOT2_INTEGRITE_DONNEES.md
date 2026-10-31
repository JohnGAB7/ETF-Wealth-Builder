# Lot 2 — Intégrité des données

Branche : `claude/project-thread-mw0vfh` (repartie de master après la fusion du lot 1) · Référence : audit, constats C3, M4, M5 (NaN), M2 (CPI)

Rédigé pour une relecture croisée (ChatGPT) et pour JG.

## Ce qui change dans les résultats

Ce lot **peut modifier des signaux**, toujours dans le sens de la prudence :
- la couverture fondamentale baisse quand le fichier de constituants est partiel (elle était surestimée) ;
- une composante de valorisation peut disparaître si des valeurs implausibles sont exclues ;
- un signal d'examen est bloqué si le dernier cours date de plus de 5 jours.

Aucun seuil existant ni poids du score n'est modifié. Un seul paramètre est **ajouté** : `max_price_age_days: 5` dans `config/strategy.yaml`. Il applique une règle déjà écrite dans `MODEL_GOVERNANCE.md` (« Never alert BUY if data are stale »).

## Fichiers modifiés

| Fichier | Changement |
|---|---|
| `src/data/holdings.py` (nouveau) | Chargement des constituants **sans renormalisation**. Unité des poids déclarée (`.meta.yaml`) ou déduite (poids max > 1 ⇒ %). Métadonnées `as_of` et `source`. Avertissements : fichier manquant, somme > 102 %, unité déduite |
| `src/data/valueinvesting.py` | Couverture divisée par max(1, somme du fichier), c'est-à-dire par l'ETF entier. Part du fichier dans l'ETF. Upsides avec \|valeur\| > 300 % exclus et comptés |
| `src/main.py` | Nouveau chargeur. Âge du cours, avec blocage du signal si le cours est ancien. Métadonnées des constituants et horodatage `retrieved_at` dans le rapport et l'e-mail |
| `src/data/macro_data.py` | CPI US en **glissement annuel** (comparé au même mois un an plus tôt, sinon `None`). Historique FRED limité à 5 ans |
| `src/reporting/report.py` | JSON strict : NaN et inf remplacés par `null` |
| `src/notifications/view_model.py`, `render.py`, `preview.py` | Affichage : fichier de constituants (part, date, source), valorisations implausibles, motif « cours ancien », observations macro anciennes, heure de récupération |
| `config/strategy.yaml` | Ajout de `max_price_age_days: 5` |
| `data/constituents/README.md`, `docs/MODEL_GOVERNANCE.md` | Documentation des règles ci-dessus |
| `tests/test_data_integrity.py` (nouveau), `tests/test_main_pipeline.py` | 11 tests ajoutés |

## Hypothèses

- `upside_dcf_ebitda_10` est une **fraction** (0,25 = 25 %). Ce n'est pas vérifié, faute d'accès à l'API. Si c'est un pourcentage, toutes les valeurs > 300 seront exclues et la couverture tombera visiblement à 0 % : l'erreur devient visible au lieu de saturer le score.
- Seuils d'ancienneté macro, pour l'affichage seulement : 10 jours (série quotidienne), 100 jours (mensuelle), 240 jours (trimestrielle), comptés depuis le début de la période. Les retards de publication sont inclus.
- 5 jours calendaires pour le cours couvrent un week-end prolongé.

## Limites connues

- Les fichiers de constituants ne sont toujours pas dans le dépôt. JG doit les fournir (fichiers des émetteurs + `.meta.yaml`).
- Les appels Finnhub par constituant ne sont pas encore limités (constat E4) ; prévu dans un lot ultérieur.
- Pas encore de dates de publication ALFRED ni d'archive des vintages (lot 4, validation).
- Le poids de la valorisation dans le score ne dépend pas encore de sa couverture (décision humaine, voir ci-dessous).

## Tests

- `python -m compileall -q src tests` : OK
- `pytest` : **50 tests passent** (39 avant ce lot).

## Décisions nécessitant une validation humaine

1. Confirmer l'unité de `upside_dcf_ebitda_10` avec un exemple de réponse de l'API (sans clé).
2. Valider `max_price_age_days: 5`.
3. Faut-il pondérer la composante de valorisation par sa couverture ? Aujourd'hui, 2 % de couverture pèse autant que 60 %. Cela modifie le score, donc la décision vous revient.

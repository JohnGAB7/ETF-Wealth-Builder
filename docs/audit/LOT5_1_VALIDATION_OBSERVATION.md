# Lot 5.1 : validation walk-forward purgée, en mode observation

- Date : 2026-11-01
- Branche : `claude/project-thread-mw0vfh`
- Conception de référence : `docs/audit/LOT5_REPONSE_REVUE_CHATGPT.md`, sections 3.1 à 3.6.
- Validation humaine : JG a donné son feu vert au mode observation le 01/11/2026.

## Ce qui change, et ce qui ne change pas

- **Aucun signal n'est modifié.** Le modèle de production (`fit_predict`), ses
  hyperparamètres, les seuils de `strategy.yaml` et la logique `classify_signal` sont
  inchangés.
- Chaque ETF reçoit en plus un bloc `validation_oos` : un test hors échantillon purgé du
  modèle actuel. Ce bloc apparaît dans le rapport JSON et dans l'e-mail, et aucune
  décision ne le lit.
- Un **statut proposé** (`VALIDATED` / `NOT_VALIDATED` / `INSUFFICIENT_HISTORY`) est
  calculé avec les critères proposés, et affiché comme tel (« critères proposés, pas encore
  appliqués »). Son activation relève du lot 5.3, après décision de JG.

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/models/validation.py` (nouveau) | Découpage purgé, références, métriques, bootstrap, Diebold-Mariano, statut proposé |
| `src/state/validation_cache.py` (nouveau) | Cache hebdomadaire `data/state/validation_cache.json` |
| `src/main.py` | `observe_validation()` : calcul ou lecture du cache ; résultat ajouté à chaque ETF |
| `config/strategy.yaml` | Blocs `validation` (paramètres) et `validation_gate_proposed` (critères en attente de décision) |
| `src/notifications/view_model.py`, `render.py` | Encadré « Test hors échantillon » (HTML et texte) |
| `src/notifications/preview.py` | Scénarios fictifs avec un test non validé et un historique court |
| `tests/test_validation.py` (nouveau), `tests/test_main_pipeline.py`, `tests/conftest.py` | Tests |

## Protocole implémenté

1. **Découpage.** Fenêtre d'entraînement croissante, blocs de test de 126 séances. Le premier
   bloc commence à `minimum_training_rows + h`.
2. **Purge.** L'entraînement d'un bloc qui commence en `t0` s'arrête à `t0 − h − 1`. La
   fenêtre du label d'entraînement le plus récent se termine donc avant le premier prix
   du test. Test : `test_purge_removes_every_overlapping_training_label`.
3. **Calibration interne purgée.** Le RandomForest est calibré (sigmoïde) sur trois plis
   internes, avec `h` lignes retirées entre la partie d'apprentissage et la partie de
   calibration. Test : `test_inner_calibration_folds_are_purged`.
4. **Pas d'embargo pour la boucle externe.** Avec une fenêtre croissante, l'entraînement ne
   contient jamais de données postérieures au test.
5. **Références** évaluées sur les mêmes blocs :
   - la fréquence de base de l'entraînement de chaque bloc (climatologie) ;
   - une régression logistique standardisée L2 (C = 1).
6. **Métriques** sur l'ensemble des prédictions hors échantillon :
   - Brier, BSS contre la climatologie (et BSS de la logistique) ;
   - log loss (probabilités bornées à [0,001 ; 0,999]) ;
   - AUC ;
   - tableau de calibration en 5 classes de quantiles, pente et ordonnée de calibration ;
   - erreur absolue moyenne de `expected_return` contre une prévision constante.
7. **Dépendance des labels.**
   - `n_eff = lignes hors échantillon / h` ;
   - IC à 90 % du BSS par bootstrap en blocs mobiles de longueur `h` (1 000 tirages,
     graine 42) ;
   - statistique de Diebold-Mariano avec variance de Newey-West à `h − 1` retards (p-valeur
     unilatérale).
8. **Stabilité.** BSS par bloc et part des blocs à BSS positif. BSS par régime, à titre
   descriptif : terciles de volatilité 63 j, drawdown au-delà de 10 %, position par rapport
   à la MM200.
9. **Hypothèse 2.3.** Le rapport contient la fréquence observée des hausses
   (`base_rate_oos`), la part des prédictions du modèle au-dessus du seuil de 0,62
   (`share_model_above_threshold`) et la même part pour la climatologie.

## Cache et coût

- Le calcul complet prend environ 25 s par ETF (mesure locale sur 1 800 séances), soit
  environ 4 minutes pour 9 ETF.
- Il n'est refait que si le résultat a au moins `refresh_days` jours (7 par défaut) ou si
  l'empreinte change : symbole, première date, horizon, longueur de bloc, version du
  protocole.
- Le cache vit dans `data/state/` comme l'état des alertes. Il bénéficie donc du même cache
  GitHub Actions.
- En cas d'erreur, le bloc vaut `{"status": "ERROR"}`. Le cycle quotidien continue et
  l'e-mail affiche « test indisponible ».

## Résultat sur données réelles : pas encore disponible

Yahoo Finance n'est pas joignable depuis mon environnement de développement (proxy 403).
Les premiers chiffres réels, dont la réponse à l'hypothèse 2.3, sortiront à la prochaine
exécution du workflow quotidien. On les trouvera dans le rapport JSON (artefact) et dans
l'e-mail. Sur une marche aléatoire simulée (1 800 séances), le protocole donne :

- BSS de +0,003, avec un IC à 90 % de [−0,094 ; +0,122] ;
- n_eff = 15,5 et 8 blocs ;
- une pente de calibration de 0,15 ;
- un statut proposé `NOT_VALIDATED`.

C'est le comportement attendu en l'absence de signal.

## Tests ajoutés

`tests/test_validation.py` (16 tests, environ 2 s, régression logistique en guise de modèle
rapide). Ils couvrent :

- la purge externe et la purge interne, un écart de purge égal à `h`, des blocs contigus ;
- l'absence de bloc si l'historique est trop court ;
- le fait que des labels qui se chevauchent rendent un découpage non purgé optimiste ;
- les métriques de base, un bootstrap reproductible qui encadre l'estimation, le signe du
  test de Diebold-Mariano, une pente de calibration proche de 1 pour des prévisions
  calibrées ;
- une marche aléatoire qui donne `NOT_VALIDATED`, et un signal implanté qui donne
  `VALIDATED` ;
- une climatologie calculée sur l'entraînement seul, des motifs explicites pour le statut
  proposé ;
- le cache : fraîcheur, empreinte, fichier illisible.

Dans `tests/test_main_pipeline.py` :

- La validation est remplacée par un substitut qui répond toujours `NOT_VALIDATED`. Les
  alertes REVIEW forcées sont malgré tout envoyées, ce qui prouve que le mode observation ne
  bloque rien.
- Un second passage le même jour réutilise le cache, sans nouveau calcul.

`tests/conftest.py` : le cache de validation est redirigé vers un dossier temporaire.

## Limites connues

- `n_eff = n / h` est une approximation, sans estimation de l'autocorrélation réelle des
  pertes (question 7 pour ChatGPT).
- Le statut proposé repose sur des critères qui ne sont pas encore validés.
- Les régimes sont descriptifs : deux ou trois épisodes de stress ne fondent pas une règle.
- Le bootstrap en blocs mobiles suppose une stationnarité approximative des pertes.
- La validation porte sur le classifieur. `expected_return` n'est mesuré que par son erreur
  absolue, sans intervalle de confiance.

## Décisions humaines toujours ouvertes

Elles sont reprises de la section 6 du document de conception. Les points 1 (critères du
statut validé), 2 (effet d'un modèle non validé) et 3 (seuil de probabilité) gagnent à être
tranchés après lecture des premiers résultats réels.

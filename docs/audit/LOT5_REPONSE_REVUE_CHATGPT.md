# Lot 5 : réponse à la revue croisée et proposition de conception

- Date : 2026-11-01
- Base : `master` à `8328956`, qui inclut la PR #5 (fichiers de constituants)
- Statut : document de conception. Aucun code de décision n'est modifié dans cette PR.
- Destinataires : JG (décisions) et ChatGPT (second reviewer quantitatif).

Ce document répond point par point à la revue. Pour chaque constat, il dit si je le
confirme dans le code, puis il propose une méthodologie, les tests et les décisions
humaines nécessaires. Les seuils de stratégie restent inchangés tant qu'ils ne sont pas validés.

---

## 0. Synthèse

Je confirme tous les constats de la revue. Je n'en conteste aucun sur le fond. J'apporte
deux nuances : la PR #5, mergée après la revue, a déjà traité une partie du point Finnhub,
et deux limites pratiques s'appliquent à l'analyse par régimes et au regroupement des ETF.

J'ajoute aussi huit constats que la revue ne mentionne pas (section 2). Trois d'entre eux
pèsent directement sur la fiabilité des signaux :

1. **La validation actuelle repose sur 8 à 9 fenêtres réellement indépendantes**, pas sur
   540 observations. Le Brier affiché n'a donc aucune portée statistique.
2. **Il existe une fuite d'information à la frontière train/test.** Les 63 dernières lignes
   d'entraînement ont des labels calculés avec des prix de la période de test.
3. **Le seuil de probabilité (0,62) est probablement inférieur à la fréquence historique**
   des rendements positifs à 63 séances. Si c'est le cas, la condition de probabilité ne
   filtre presque rien. C'est une hypothèse, à mesurer sur données réelles au lot 5.1.

Risque principal, par ordre d'importance : aujourd'hui, un `BUY_OPPORTUNITY_REVIEW` peut
être émis par un modèle sans capacité prédictive démontrée, avec une couverture de données
qui atteint le seuil sans aucune donnée fondamentale propre à l'ETF.

Je propose de ne pas réécrire le modèle. Je propose plutôt de construire autour de lui un
moteur de validation en mode observation, puis une gouvernance qui bloque prudemment
(« fail closed »). Les règles de blocage ne s'activent qu'après validation des critères par JG.

---

## 1. Avis sur chaque constat de la revue

### P0 — Validation statistique et gouvernance des signaux : **confirmé**

Ce que montre le code (`src/models/probabilistic.py`) :

- Un découpage chronologique unique 75 / 25 (`split = int(len(data) * 0.75)`).
- Une calibration `CalibratedClassifierCV(cv=TimeSeriesSplit(3))` sans purge ni embargo.
  Les plis internes ont le même chevauchement de labels.
- Des labels `positive_forward_return` calculés sur `close.shift(-63)`. Deux lignes
  consécutives partagent 62 des 63 séances de leur fenêtre.
- `main.py` émet un signal à partir de `prob_positive`, quel que soit le résultat de
  `model_quality()`. Ce résultat n'est qu'affiché dans l'e-mail.
- Les paramètres `walk_forward_test_fraction` et `minimum_validation_rows` de
  `config/strategy.yaml` ne sont lus nulle part. Les valeurs 0,75 et 50 sont codées en dur.

J'approuve la remarque « un Brier inférieur à la référence sur une seule période ne prouve
rien ». Elle est même plus forte qu'il n'y paraît (voir 2.1).

### P1 — Couverture des données : **confirmé, avec un exemple chiffré**

`main.py`, lignes 141 à 147 : `coverage = 0,45 + 0,15·valo + 0,10·analystes + 0,15·news + 0,15·macro`.

Prenons un ETF sans valorisation ni analystes, par exemple EMIM, qui n'a pas de fichier de
constituants. Avec des actualités générales disponibles et une macro complète, sa couverture
vaut 0,45 + 0,15 + 0,15 = **0,75**. C'est au-dessus du seuil `minimum_data_coverage: 0,70`.
Les actualités Finnhub `category=general` sont les mêmes pour tous les ETF. Elles ne disent
rien de propre à un ETF donné. Je confirme qu'elles ne doivent pas compter comme couverture
spécifique.

### P1 — Appels Finnhub : **confirmé en partie, déjà en partie corrigé**

La revue porte sur les quatre premiers lots. La PR #5, mergée ensuite, a ajouté :

- une interrogation limitée aux 25 plus grosses lignes par ETF (`MAX_ANALYST_CONSTITUENTS`) ;
- une mémoire par ticker pendant une exécution ;
- un espacement de 1,1 s entre appels (quota gratuit de 60 appels par minute) ;
- une mémoire équivalente pour ValueInvesting.io.

Le volume maximal est donc de 9 × 25 = 225 appels avant dédoublonnage. Les grandes
capitalisations sont communes à la plupart des ETF, ce qui ramène le nombre probable à
moins de 100 appels.

Il reste à faire :

- un cache persistant avec durée de validité configurable ;
- le rejet des recommandations anciennes (aujourd'hui `rows[0]` est pris sans regarder
  le champ `period`) ;
- une couverture calculée seulement sur les recommandations valides et récentes
  (aujourd'hui, toute réponse non vide compte) ;
- un traitement explicite des réponses 429, avec un budget d'appels par exécution.

### P1 — Validation des fichiers de constituants : **confirmé, avec une nuance**

`src/data/holdings.py` signale `weights_exceed_100pct` au-delà de 1,02, mais le fichier
reste utilisé. Le dénominateur devient alors la somme du fichier. Je confirme qu'une règle
de quarantaine est préférable.

Nuance sur les doublons : `GOOGL` et `GOOG`, ou `BRK/A` et `BRK/B`, sont des lignes
distinctes et légitimes. Seul le même ticker répété sur le même marché est un doublon.

### P2 — Devises : **confirmé**

`currency` mélange plusieurs notions. CSPX.L est en USD alors que les autres lignes sont
en EUR, donc les comparaisons de performance entre lignes ne sont pas homogènes aujourd'hui.
EMIM.AS en EUR est bien une cotation en euros, mais le fonds n'est pas couvert : le risque
de change des devises émergentes reste entier.

### P2 — Persistance et concurrence des alertes : **confirmé**

- `daily_monitor.yml` n'a pas de bloc `concurrency`. Deux exécutions (cron et manuelle)
  peuvent restaurer le même état. La dernière sauvegarde écrase alors l'autre.
- L'état n'est sauvegardé qu'en fin d'exécution (`save_state` après le digest). Un arrêt
  après l'envoi d'une alerte et avant la sauvegarde provoque un doublon le lendemain.
- Le cache GitHub est supprimé après 7 jours sans accès. La perte d'état produit au plus
  une alerte en double par épisode BUY en cours. C'est gênant, sans être dangereux.

### P2 — Identité des nouvelles lignes ETF : **confirmé**

Le contrôle de clé ISIN est purement syntaxique. Rien ne vérifie que `SPYL.DE` désigne bien
le fonds `IE000XZSV718`. Je confirme aussi la distinction core / comparateur / satellite :
SEC0 est un pari sectoriel concentré, pas une alternative à VWCE.

### Deux nuances sur la méthodologie demandée

1. **L'analyse par régimes restera descriptive.** Sur 7 à 15 ans d'historique, il n'y a
   que deux ou trois épisodes de stress (2020, 2022). Une performance par régime calculée
   sur deux épisodes est anecdotique. Je propose de l'afficher sans en faire un critère
   bloquant.
2. **Regrouper les ETF n'augmente presque pas l'information.** VWCE, IWDA, SPPW, SPYY, CSPX
   et SPYL sont corrélés à plus de 0,9. Valider sur six ETF presque identiques revient à
   valider une seule fois. Il faut au contraire traiter ce regroupement comme un risque
   de surconfiance.

---

## 2. Constats supplémentaires

| # | Constat | Gravité | Fichier |
|---|---|---|---|
| 2.1 | Nombre effectif d'observations indépendantes ≈ test_rows / 63 ≈ 8 à 9 | P0 | probabilistic.py |
| 2.2 | Fuite à la frontière train/test : pas de purge des 63 dernières lignes d'entraînement | P0 | probabilistic.py |
| 2.3 | Seuil `probability_buy_threshold` 0,62 probablement inférieur à la fréquence de base | P0 (hypothèse à mesurer) | strategy.yaml |
| 2.4 | `expected_return` jamais validé ; régresseur entraîné sur train seul, classifieur réentraîné sur tout | P1 | probabilistic.py |
| 2.5 | `downside_risk` toujours `None` : son poids (0,15) est redistribué en silence | P1 | main.py, opportunity.py |
| 2.6 | La renormalisation du score augmente le poids des autres composantes quand la valorisation manque | P1 | opportunity.py |
| 2.7 | Paramètres de validation de `strategy.yaml` non utilisés | P2 | probabilistic.py |
| 2.8 | Plusieurs lignes récentes (SPYL, SPPW, SEC0) ont un historique court, à mesurer | P2 | etf_universe.yaml |

Explications :

- **2.1** Avec des labels à 63 séances qui se chevauchent, 540 lignes de test ne contiennent
  qu'environ 540 / 63 ≈ 8,6 fenêtres disjointes. L'écart type d'un Brier sur 9 tirages est
  du même ordre que l'écart entre le modèle et la référence affichée dans les aperçus
  (0,221 contre 0,236). Il est impossible de distinguer ce résultat du hasard.
- **2.3** Sur les marchés actions mondiaux, la part des fenêtres de 63 séances à rendement
  positif est historiquement d'environ 65 à 70 %. Ce chiffre est une estimation de mémoire
  et doit être mesuré. Si c'est le cas, une probabilité de 0,62 est *inférieure* à la
  fréquence inconditionnelle, et la condition `prob ≥ 0,62` est remplie presque tout le
  temps. Le signal REVIEW repose alors en pratique sur le seul score. Je ne propose pas de
  changer le seuil. Je propose de mesurer, puis de soumettre à JG une condition exprimée en
  écart à la fréquence de base.
- **2.6** Exemple : sans valorisation (poids 0,20) ni risque baissier (0,15), les poids
  restants (0,65) sont ramenés à 1. La probabilité passe de 25 % à 38 % du score. Une
  donnée manquante change ainsi la nature du score, sans que cela soit visible.

---

## 3. Méthodologie proposée

### 3.1 Validation walk-forward purgée avec embargo

- **Schéma.** Fenêtre d'entraînement croissante, blocs de test successifs de 126 séances
  (6 mois, paramètre `walk_forward_test_block_days`). Le premier bloc commence après
  `minimum_training_rows`.
- **Purge.** Pour un bloc de test qui commence en `t0`, on retire de l'entraînement toute
  ligne `t` telle que `t + h > t0 - 1`, avec `h` = 63. Cela revient à supprimer les 63
  dernières lignes avant le test. Aucun label d'entraînement n'utilise alors un prix du bloc de test.
- **Embargo.** Avec une fenêtre croissante, l'entraînement ne voit jamais de données
  postérieures au test : l'embargo est sans objet pour le schéma principal. Il s'applique
  en revanche aux plis de calibration internes. La calibration utilise un découpage interne
  purgé lui aussi : `h` lignes retirées entre le sous-ensemble d'apprentissage et le
  sous-ensemble de calibration.
- **Prédictions hors échantillon.** Chaque ligne de test reçoit une probabilité issue d'un
  modèle qui ne l'a jamais vue. Les métriques sont calculées par bloc, puis sur l'ensemble
  des prédictions hors échantillon.
- **Modèle inchangé.** Le RandomForest calibré et ses hyperparamètres restent tels quels.
  Seule la manière de le valider change.

### 3.2 Références comparées

1. **Fréquence de base** : la fréquence des labels positifs dans l'entraînement de chaque
   bloc, appliquée comme constante (« climatologie »). C'est la référence du Brier Skill Score.
2. **Régression logistique** : standardisation puis L2 (C = 1), mêmes variables, même
   protocole purgé. Elle indique si la complexité du RandomForest apporte quelque chose.
3. Le modèle actuel.

### 3.3 Métriques

- Brier score, et **Brier Skill Score** `BSS = 1 − Brier_modèle / Brier_référence`, par bloc
  et global.
- Log loss, avec des probabilités bornées à [0,001 ; 0,999] et ce bornage documenté.
- Calibration : tableau de fiabilité en 5 classes (pas 10, l'échantillon est trop petit),
  plus la pente et l'ordonnée à l'origine de calibration.
- AUC, à titre secondaire seulement.
- Pour `expected_return` : erreur absolue moyenne comparée à une prévision constante (le
  rendement moyen d'entraînement). Corrige 2.4.

### 3.4 Dépendance des labels et incertitude

- **Nombre effectif** affiché : `n_eff = n_test / h`, soit le nombre de fenêtres disjointes.
  C'est une approximation simple et prudente.
- **Intervalle de confiance du BSS** par bootstrap en blocs mobiles, avec des blocs de
  longueur `h` et 1 000 tirages, sur la différence de pertes `Brier_ref − Brier_modèle`
  ligne à ligne.
- **Test de Diebold-Mariano** sur la même différence, avec une variance HAC de Newey-West
  (`h − 1` retards), comme confirmation.

### 3.5 Stabilité

- La part des blocs où le BSS est positif.
- Le BSS par régime, descriptif uniquement (voir la nuance 1) :
  - volatilité réalisée en terciles ;
  - drawdown supérieur à 10 % ou non ;
  - prix au-dessus ou en dessous de la MM200.

### 3.6 Gouvernance des signaux (fail closed)

Un nouveau statut de modèle est calculé : `VALIDATED`, `NOT_VALIDATED` ou
`INSUFFICIENT_HISTORY`. Les critères proposés sont des **valeurs à valider par JG** :

| Critère | Proposition |
|---|---|
| Nombre effectif de fenêtres hors échantillon | `n_eff ≥ 20` |
| BSS global contre la fréquence de base | borne basse de l'IC à 90 % > 0 |
| Stabilité | BSS > 0 dans au moins 60 % des blocs |
| Contre la régression logistique | Brier du modèle ≤ Brier logistique + 0,005 |
| Calibration | pente entre 0,5 et 1,5 |

Conséquence sur les signaux, si JG la valide :

- `VALIDATED` : aucun changement.
- `NOT_VALIDATED` : un `BUY_OPPORTUNITY_REVIEW` devient `WATCH`, avec la raison « modèle
  sans capacité prédictive démontrée ». La probabilité affichée devient la fréquence
  historique, présentée comme telle.
- `INSUFFICIENT_HISTORY` : `INSUFFICIENT_EVIDENCE`, comme aujourd'hui.

**Conséquence attendue, à dire franchement.** Avec 7 à 15 ans de données, `n_eff` tourne
autour de 20 à 50, et des variables uniquement techniques ont rarement un pouvoir prédictif
robuste à 3 mois. Il est probable que le modèle soit `NOT_VALIDATED` pour la plupart des
ETF, et que les REVIEW disparaissent presque complètement. Je considère que c'est le
comportement correct : la stratégie DCA de long terme n'en dépend pas, et un signal non
démontré ne doit pas être présenté comme prioritaire.

**Coût de calcul.** Un walk-forward d'environ 10 blocs × 9 ETF multiplie le temps
d'entraînement par 10. La CI dure déjà environ 4 minutes. Je propose de calculer la
validation une fois par semaine, ou quand l'historique change de plus de N séances, et de
la mettre en cache avec sa date et l'empreinte des données. L'inférence quotidienne
réutilise ce statut, et l'e-mail affiche la date de la dernière validation.

### 3.7 Nouvelle architecture de qualité des données

Je remplace l'indice unique par un bloc `data_quality` par source, chacun avec un statut
explicite :

```
price:        ok | stale | missing          (âge, longueur d'historique)
model:        VALIDATED | NOT_VALIDATED | INSUFFICIENT_HISTORY
constituents: ok | stale | quarantined | missing   (date, poids total, raisons)
valuation:    poids couvert / poids total ETF, nb de lignes exclues
analysts:     poids couvert par des recommandations valides et récentes
macro:        part des séries fraîches (dates d'observation conservées)
news:         contexte de marché général, n'entre dans aucune couverture d'ETF
```

Chaque type de signal a ses **prérequis explicites** :

| Signal | Prérequis proposés |
|---|---|
| `BUY_OPPORTUNITY_REVIEW` | price ok, model VALIDATED, constituents ok, valorisation ≥ seuil (à décider), macro ≥ 50 % fraîche |
| `WATCH` | price ok, model au moins NOT_VALIDATED |
| `REGULAR_DCA` | price ok |
| `INSUFFICIENT_EVIDENCE` | sinon |

Transition : l'ancien indice et la nouvelle grille sont calculés en parallèle pendant
quelques semaines (mode observation). Le rapport JSON contient les deux, et un tableau liste
les signaux qui changeraient. La bascule n'a lieu qu'après validation.

Question ouverte : un ETF structurellement sans valorisation possible, comme EMIM (quasiment
aucune ligne US/CA), peut-il un jour recevoir un REVIEW ? Ma recommandation est non, avec un
statut « valorisation non disponible pour ce marché » clairement affiché.

### 3.8 Contrôle des fichiers de constituants

| Situation | Règle proposée |
|---|---|
| Somme des poids > 102 % | **quarantaine** : fichier exclu de la valorisation et des analystes |
| Même ticker répété sur le même marché | quarantaine (ou agrégation si même ISIN, à décider) |
| `weight_unit` absent du `.meta.yaml` | quarantaine (fin de l'inférence silencieuse) |
| `as_of` absent | quarantaine |
| `as_of` > 120 jours | avertissement « composition ancienne » ; > 200 jours : quarantaine |
| Marché non reconnu | ligne exclue de ValueInvesting (déjà le cas), poids rapporté |
| `completeness: full` déclaré mais somme < 95 % | avertissement « fichier incomplet » |

Le motif de quarantaine apparaît dans l'e-mail. Un fichier en quarantaine n'est jamais
renormalisé ni « réparé ».

---

## 4. Plan de correction proposé

| Lot | Contenu | Modifie les signaux ? |
|---|---|---|
| **5.1** | Moteur de validation purgée (3.1 à 3.5), en observation : métriques dans le rapport et l'e-mail, en cache hebdomadaire | Non |
| **5.2** | Grille de qualité des données (3.7) et contrôle des constituants (3.8), en observation, avec le tableau des signaux qui changeraient | Non |
| **5.3** | Activation de la gouvernance (3.6) et des prérequis (3.7), une fois les critères validés par JG ; tests de non-régression | **Oui, après validation** |
| 6 | Finnhub : cache persistant avec durée de validité, rejet des recommandations anciennes, 429, budget | Non |
| 7 | Devises : champs distincts, EUR comme devise de référence, conversion BCE pour les comparaisons | Non |
| 8 | Concurrence et état : bloc `concurrency`, sauvegarde après chaque envoi, stratégie de reprise | Non |
| 9 | Identité des ETF (contrôle du symbole et de la devise via le fournisseur, historique minimal) et rôles core / comparateur / satellite | Possible pour les satellites (décision) |

Le lot 8 est très court et sans effet sur les décisions (une ligne `concurrency` et un
déplacement de `save_state`). Il peut passer avant le lot 5.1 si JG le souhaite.

---

## 5. Tests prévus

Validation (5.1) :

- **Purge** : aucune ligne d'entraînement n'a un label dont la fenêtre chevauche le bloc de test.
- **Absence de fuite** : avec une variable qui encode le futur, le score s'effondre
  après purge alors qu'il est parfait sans purge.
- **Marche aléatoire** : sur des prix simulés sans signal, BSS ≈ 0, IC contenant 0, statut
  `NOT_VALIDATED`.
- **Signal implanté** : sur une série où une variable prédit le label, statut `VALIDATED`.
- **n_eff** : la valeur calculée est égale à `n_test / h`.
- **Bootstrap** : graine fixe, résultat reproductible.
- **Références** : la référence de fréquence de base n'utilise que des données
  d'entraînement.

Gouvernance (5.3), tests de non-régression des décisions :

- Jeu de cas figés (« golden ») : pour chaque combinaison statut modèle × qualité des
  données × score × probabilité, le signal attendu.
- `NOT_VALIDATED` avec un score de 90 et une probabilité de 0,8 donne `WATCH`, jamais REVIEW.
- Les actualités générales seules ne font jamais franchir un prérequis.
- Un fichier de constituants en quarantaine fait tomber la valorisation à « indisponible »,
  jamais à 0 % d'upside.
- Les seuils de `strategy.yaml` sont lus depuis la configuration : un test échoue si une
  valeur est codée en dur.

Constituants (5.2) : un cas par ligne du tableau 3.8.

Toujours : aucun appel réseau, aucun e-mail réel (garde-fous de `tests/conftest.py`).

---

## 6. Décisions humaines (JG)

1. **Critères du statut `VALIDATED`** (tableau 3.6) : valeurs proposées ou autres.
2. **Effet d'un modèle non validé** : REVIEW ramené à WATCH (recommandé) ou à
   INSUFFICIENT_EVIDENCE.
3. **Seuil de probabilité** : après mesure de la fréquence de base, l'exprimer en écart à
   cette fréquence ? Aucune modification sans accord.
4. **REVIEW sans valorisation possible** (EMIM) : non (recommandé) ou oui.
5. **Seuil minimal de couverture de valorisation** pour un REVIEW.
6. **Âge maximal des compositions** : 120 jours pour l'avertissement, 200 pour la quarantaine.
7. **Satellites (SEC0)** : REVIEW autorisé ou limité à WATCH ?
8. **Devise de référence** : EUR.
9. **Fréquence de validation** : hebdomadaire, avec cache.
10. **Ordre des lots** : faire passer le lot 8 (concurrence) en premier ?

---

## 7. Points pour la relecture de ChatGPT

- Purge seule pour le schéma à fenêtre croissante, embargo réservé à la calibration
  interne : est-ce suffisant, ou faut-il une validation croisée combinatoire purgée (CPCV) ?
- `n_eff = n_test / h` contre une estimation par autocorrélation des résidus de perte :
  laquelle afficher ?
- Bootstrap en blocs mobiles de longueur `h` contre bootstrap stationnaire.
- Le critère « BSS > 0 dans 60 % des blocs » est-il pertinent avec des blocs de 126 séances
  (2 fenêtres indépendantes par bloc) ?

# Lot 2b : fichiers de constituants des 8 ETF actions

Date : 2026-10-31. Branche : `claude/project-thread-mw0vfh`.

## Objet

Alimenter la valorisation par constituants (ValueInvesting.io, US/Canada uniquement) et
les recommandations d'analystes avec les fichiers publiés par les émetteurs, sans
gonfler la couverture. EMIM/EIMI n'a pas de fichier : quasi aucune ligne US/CA.

## Fichiers produits

| ETF | Source | Date | Lignes | Poids du fichier | Poids US/CA | US/CA avec ticker |
|---|---|---|---|---|---|---|
| VWCE | Vanguard | 30/09/2026 | 3 726 | 99,42 % | 64,86 % | 64,86 % |
| IWDA | iShares (SWDA) | 29/10/2026 | 1 201 | 99,60 % | 76,13 % | 76,13 % |
| CSPX | iShares | 29/10/2026 | 503 | 99,90 % | 99,90 % | 99,90 % |
| IUSN | iShares (WSML) | 29/10/2026 | 3 267 | 99,49 % | 65,75 % | 65,75 % |
| SEC0 | iShares (SEMI) | 29/10/2026 | 231 | 99,65 % | 64,66 % | 64,66 % |
| SPYY | SSGA | 29/10/2026 | 2 228 | 100,00 % | 68,00 % | 67,84 % |
| SPPW | SSGA | 29/10/2026 | 1 236 | 100,00 % | 76,49 % | 76,30 % |
| SPYL | SSGA | 29/10/2026 | 504 | 100,00 % | 100,00 % | 99,86 % |

Tous les pourcentages sont exprimés par rapport au poids total de l'ETF. Les lignes de
liquidités, devises, futures et monétaire sont retirées et non redistribuées.

## Choix

1. Convertisseur `src/data/holdings_import.py` (iShares CSV, SSGA xlsx, Vanguard xlsx),
   réutilisable à chaque mise à jour trimestrielle. Les fichiers bruts ne sont pas commités.
2. `market = US/CA` seulement si le pays de la société ET la place de cotation sont US/CA
   (iShares). Une société néerlandaise cotée au NASDAQ reste `Netherlands`. Vanguard ne
   donne pas la place : le code pays est utilisé. SSGA : pays, puis place iShares si
   correspondance trouvée.
3. SSGA ne publie pas de ticker. Un ticker iShares du même jour est repris seulement si
   pays, prix (après facteur de devise par pays, tolérance 0,5 %) et nom concordent.
   Sinon l'ISIN reste l'identifiant et la ligne n'est valorisée par aucun fournisseur.
   Contrôle manuel des 1 152 correspondances SPYY : les 31 cas où le premier mot diffère
   sont tous corrects (McDonald's, L'Oréal, GSK, Novonesis...).
4. Volume d'appels API : avec ~13 000 lignes, le code aurait fait un appel Finnhub par
   ligne et par jour. Désormais :
   - Finnhub : seules les 25 plus grosses lignes de chaque ETF, appels espacés de 1,1 s,
     mémorisés pour la durée de l'exécution (Apple n'est demandé qu'une fois) ;
   - ValueInvesting.io : chaque ticker n'est demandé qu'une fois par exécution.
   La couverture analystes baisse en conséquence et reste affichée telle quelle.

## Limites

- Tickers conservés tels que publiés (`BRK B` chez iShares, `BRK/B` chez Vanguard). Un
  fournisseur peut ne pas les reconnaître : la couverture affichée baisse, rien n'est inventé.
- Vanguard : 11 lignes sans ticker (≈ 0,2 %) sont ignorées.
- Le fichier VWCE est au 30/09/2026 (publication mensuelle Vanguard), les autres au 29/10.
- Les compositions actuelles ne représentent pas les compositions passées.

## Décisions humaines

- Valider le plafond de 25 lignes pour Finnhub (paramètre `MAX_ANALYST_CONSTITUENTS`).
- Rythme de mise à jour des fichiers (proposition : trimestriel).

## Tests

`tests/test_holdings_import.py` : filtrage actions, poids non renormalisés, règle US/CA,
correspondance SSGA (y compris faux positif au même prix), lecture Vanguard, plafond
Finnhub, mémorisation ValueInvesting. Aucun appel réseau, aucun e-mail.

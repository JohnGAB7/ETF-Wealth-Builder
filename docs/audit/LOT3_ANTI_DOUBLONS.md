# Lot 3 — Anti-doublons d'alertes et évolution des statuts

Référence : audit, constat E1. Rédigé pour une relecture croisée (ChatGPT) et pour JG.

## Ce qui change

- Les paramètres `email_on_signal_upgrade_only: true` et `max_alerts_per_etf_per_day: 1` de `config/strategy.yaml` étaient ignorés. Ils sont maintenant appliqués. **Leurs valeurs ne changent pas.**
- Un ETF qui reste en « Opportunité à examiner » plusieurs jours déclenche **une seule** alerte immédiate par épisode. Le digest quotidien continue de l'afficher chaque jour.
- Le digest affiche l'évolution depuis le dernier rapport : une puce de synthèse, une flèche ▲/▼ dans la vue d'ensemble, et « Changement : … » ou « Inchangé depuis le … » sur chaque fiche.
- Les signaux eux-mêmes ne changent pas.

## Fichiers

| Fichier | Changement |
|---|---|
| `src/state/alert_state.py` (nouveau) | État JSON `data/state/alert_state.json` : dernier statut, date depuis laquelle il dure, alerte déjà envoyée pour l'épisode, compteur par jour (31 jours conservés). Écriture atomique ; un fichier absent ou corrompu repart d'un état vide |
| `src/main.py` | Statuts précédents ajoutés aux résultats (donc au rapport JSON) ; décision d'alerte avec motif (`new_episode`, `already_alerted_this_episode`, `daily_cap`, `retry_or_repeat`) ; enregistrement de l'alerte **uniquement si l'envoi a réussi** ; sauvegarde de l'état à la fin |
| `src/notifications/view_model.py`, `render.py`, `preview.py` | Affichage de l'évolution des statuts |
| `tests/test_alert_state.py` (nouveau), `tests/test_main_pipeline.py` | 8 tests ajoutés |

## Règles

- **Épisode** : suite de rapports consécutifs en « Opportunité à examiner ». Il se termine dès que le statut change.
- Si l'envoi échoue, l'épisode reste ouvert et l'alerte est retentée au cycle suivant : une alerte n'est jamais perdue.
- Une relance manuelle du workflow le même jour est bloquée par le plafond journalier.
- Persistance : le workflow `daily_monitor.yml` restaurait et sauvegardait déjà `data/state` via `actions/cache`. Rien à changer.

## Limites connues

- Le cache GitHub Actions peut être purgé (7 jours sans accès, ou limite de taille). L'état repart alors de zéro : au pire, une alerte est **répétée une fois**, jamais perdue.
- Le cache n'est sauvegardé que si le job réussit. En cas d'échec, l'état de la veille est conservé.
- « Dernier rapport » désigne le dernier cycle exécuté, y compris une relance manuelle le même jour.

## Tests

- `pytest` : **58 tests passent** (50 avant ce lot).

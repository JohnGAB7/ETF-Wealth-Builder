# Politique de sécurité

ETF Wealth Builder est un dépôt **public**. Le code, l'historique Git, les
issues, les pull requests et les journaux GitHub Actions sont visibles par
tout le monde. Ce document décrit où vivent les secrets, comment les gérer et
quels réglages GitHub doivent rester actifs.

## 1. Où vivent les secrets

Les secrets ne vivent **qu'à un seul endroit** :
**Settings → Secrets and variables → Actions** (secrets de dépôt).

| Secret | Usage |
| --- | --- |
| `VALUEINVESTING_API_KEY` | Valorisation des constituants US et Canada uniquement |
| `FRED_API_KEY` | Indicateurs macro américains |
| `FINNHUB_API_KEY` | Optionnel : actualités et recommandations d'analystes |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Envoi de l'e-mail quotidien |
| `EMAIL_FROM`, `EMAIL_TO` | Expéditeur et destinataire |

Règles :

- Ne jamais écrire une clé, un mot de passe ou une adresse privée dans le code,
  `config/`, `.env.example`, un commit, une issue, une PR ou un message de chat.
- Le fichier `.env` local est ignoré par Git (`.gitignore`). Il ne doit jamais
  être ajouté avec `git add -f`.
- Les secrets ne sont injectés que dans l'étape `Run monitor` du workflow
  `daily_monitor.yml`. Le workflow de tests (`tests.yml`), qui tourne aussi sur
  les pull requests, n'en reçoit **aucun**.
- Le code ne doit jamais afficher un secret dans les journaux. GitHub masque les
  valeurs connues, mais ce masquage ne couvre pas une valeur transformée
  (encodée, tronquée, concaténée).
- ECB Data Portal et Eurostat ne demandent aucune clé.

## 2. Mot de passe d'application pour l'e-mail

`SMTP_PASSWORD` ne doit **jamais** être le vrai mot de passe du compte e-mail.

- Activez la validation en deux étapes sur le compte d'envoi.
- Créez un **mot de passe d'application** dédié à ETF Wealth Builder :
  - Microsoft (Hotmail / Outlook.com) : compte Microsoft → Sécurité → Options
    de sécurité avancées → Mots de passe d'application.
  - Google (Gmail) : compte Google → Sécurité → Mots de passe des applications.
- Idéalement, utilisez une **adresse d'envoi dédiée** plutôt que votre boîte
  principale : en cas de fuite, seul ce compte est exposé.
- Microsoft restreint progressivement l'authentification SMTP par mot de passe
  sur les comptes personnels. Si l'envoi via Outlook.com est refusé, un compte
  Gmail dédié avec mot de passe d'application est l'alternative la plus simple.
- Les tests n'envoient jamais de vrai e-mail ; les aperçus sont générés par
  `python -m src.notifications.preview` à partir de données fictives.

## 3. Rotation des clés

- Préférez des clés **gratuites, sans moyen de paiement associé**, et limitées
  au strict nécessaire.
- Renouvelez chaque clé et le mot de passe d'application **au moins une fois
  par an**, et immédiatement en cas de doute.
- Procédure : créer la nouvelle clé chez le fournisseur → la mettre à jour dans
  Settings → Secrets → lancer `daily_monitor` manuellement (Run workflow) →
  vérifier le rapport → **révoquer l'ancienne clé** chez le fournisseur.
- Si une clé a été poussée dans Git, même brièvement, considérez-la comme
  compromise : révoquez-la d'abord. Supprimer le commit ne suffit pas, car
  l'historique public a pu être copié.

## 4. Signaler une vulnérabilité

Merci de **ne pas ouvrir d'issue publique** pour un problème de sécurité.

- Utilisez le signalement privé de GitHub : onglet **Security → Report a
  vulnerability** (Private vulnerability reporting).
- Décrivez le problème, les étapes pour le reproduire et l'impact possible.
  N'incluez aucun secret réel.
- Il s'agit d'un projet personnel maintenu bénévolement : une réponse est
  visée sous 7 jours, sans garantie de délai de correction.

## 5. Réglages GitHub recommandés

À vérifier dans **Settings** (ces réglages ne peuvent pas être appliqués par
une pull request) :

**Code security**
- Secret scanning : activé.
- Push protection : activé (bloque un push qui contient une clé reconnue).
- Dependabot alerts et Dependabot security updates : activés.
- Private vulnerability reporting : activé.

**Actions → General**
- Fork pull request workflows : *Require approval for all outside
  collaborators*.
- Workflow permissions : *Read repository contents and packages permissions*,
  et ne pas autoriser GitHub Actions à créer ou approuver des pull requests.

**Branches** (ou Rules → Rulesets) sur `master`
- Pull request obligatoire avant fusion.
- Statut `Python tests` requis.
- Force push et suppression de la branche interdits.

**Compte**
- Double authentification activée sur le compte GitHub
  (Settings → Password and authentication).

## 6. Règles pour les workflows

- Chaque workflow déclare `permissions: contents: read`. Toute permission en
  écriture doit être ajoutée au niveau du job qui en a besoin, avec un
  commentaire qui la justifie.
- Les actions sont épinglées par SHA de commit (avec la version en
  commentaire). Dependabot (`.github/dependabot.yml`) propose les mises à jour.
- `actions/checkout` utilise `persist-credentials: false` : le jeton n'est pas
  conservé dans `.git/config`.
- Ne jamais utiliser le déclencheur `pull_request_target` ni passer de secrets
  à un workflow déclenché par une pull request.
- Ne jamais interpoler directement du texte contrôlé par un tiers
  (`github.event.pull_request.title`, corps d'issue, nom de branche) dans une
  commande `run:` ; passer par une variable d'environnement.

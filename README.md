# MK Value Investing Platform

MK-VIP est une plateforme d’analyse fondamentale destinée à transformer des
données financières auditées en décisions d’investissement explicables.

La plateforme dispose maintenant d’un premier flux d’analyse exécutable :

- API Python/FastAPI ;
- PostgreSQL et migrations Alembic ;
- interface React/TypeScript ;
- comptes personnels et isolation des données par utilisateur ;
- authentification multifacteur TOTP et gestion des sessions actives ;
- import des entreprises et de leurs données financières annuelles ;
- import automatique du dernier exercice public avec repli Yahoo Finance,
  SEC EDGAR puis ESEF européen ;
- explorateur CAC 40, CAC Next 20 et SBF 120 avec ajout multiple sans saisie de
  ticker ;
- modification, archivage ou suppression d’une entreprise dans les deux vues ;
- calcul de dix ratios, six indicateurs et trois scores explicables ;
- valorisation par DCF, Owner Earnings, EPV, Graham et multiple de résultat ;
- scoring global qualité, sécurité, valeur et moat quantitatif ;
- tableau de décision, distribution des signaux et portefeuille de recherche ;
- recherche des entreprises par nom ou ticker ;
- Analyste IA sourcé pour synthétiser, comparer et interroger les dossiers ;
- quota quotidien et cache persistant de l’Analyste IA par utilisateur ;
- premiers critères Graham/Buffett issus du classeur métier ;
- tests automatisés, Docker et CI GitHub.

## Lancer la plateforme

Prérequis : Docker Desktop.

```bash
docker compose up --build
```

Puis ouvrir :

- application : <http://localhost:5173>
- documentation API : <http://localhost:8000/docs>
- santé API : <http://localhost:8000/api/v1/health>
- emails locaux Mailpit : <http://localhost:8025>

Le parcours applicatif commence par un compte personnel vérifié :

1. créer un compte, ouvrir l’email reçu dans Mailpit et suivre son lien de
   vérification ;
2. se connecter avec le compte vérifié ;
3. ouvrir « Sécurité » pour configurer le MFA, conserver les codes de
   récupération et contrôler les sessions actives ;
4. utiliser « Explorer les indices » pour sélectionner une ou plusieurs
   composantes du CAC 40, du CAC Next 20 ou du SBF 120, ou importer une
   entreprise manuellement ;
5. utiliser « Ajouter les données », puis choisir l’import public automatique
   ou la saisie manuelle d’un exercice financier normalisé ;
6. ouvrir l’analyse d’une entreprise prête pour consulter ses scores,
   indicateurs et tendances historiques ;
7. préparer une valorisation, ajuster les hypothèses et comparer les cinq
   méthodes à la capitalisation observée ;
8. calculer le scoring global et lire les quatre contributions et explications ;
9. revenir au tableau de décision pour comparer les derniers scorings, filtrer
   les signaux et rouvrir un dossier prioritaire.
10. ouvrir « Interroger l’IA » pour produire une synthèse, comparer deux
   entreprises ou poser une question sur les analyses MK-VIP disponibles.

### Tester la vérification et la réinitialisation

Le parcours local complet utilise uniquement Mailpit : aucun email ne quitte la
machine.

1. Sur <http://localhost:5173>, créer `investor@example.com` avec un mot de
   passe d’au moins 12 caractères. L’inscription répond de façon générique et
   ne connecte pas le compte.
2. Sur <http://localhost:8025>, ouvrir « Vérifie ton adresse MK-VIP », puis
   suivre le lien `#verify-email=…`. L’application retire immédiatement ce
   fragment de l’URL, vérifie le jeton, puis permet la connexion.
3. Se connecter, puis se déconnecter. Depuis l’écran de connexion, choisir
   « Mot de passe oublié », saisir la même adresse et valider la réponse
   générique.
4. Dans Mailpit, ouvrir « Réinitialise ton mot de passe MK-VIP », suivre le
   lien `#reset-password=…` et choisir un nouveau mot de passe d’au moins
   12 caractères.
5. Vérifier que toute ancienne session est révoquée et que seul le nouveau mot
   de passe permet une nouvelle connexion.

Les liens de vérification expirent après 24 heures ; ceux de réinitialisation
après 30 minutes. Chaque jeton est à usage unique. Les demandes d’email sont
limitées, par adresse et par usage, à une toutes les 60 secondes et cinq par
heure. Inscription, renvoi de vérification et demande de réinitialisation
conservent une réponse générique, que le compte existe, soit déjà vérifié ou
que la limite soit atteinte.

La configuration locale est volontairement adaptée à HTTP et à Mailpit. En
production, servir MK-VIP exclusivement en HTTPS, activer le cookie `Secure`,
remplacer `MKVIP_AUTH_EMAIL_HASH_SECRET` par un secret HMAC fort et unique,
remplacer `MKVIP_MFA_ENCRYPTION_KEY` par une clé Fernet aléatoire conservée
durablement, puis utiliser un relais SMTP authentifié avec chiffrement
STARTTLS. Voir
[`docs/authentication.md`](docs/authentication.md).

Les montants du formulaire sont exprimés en millions dans la devise de
l’entreprise. La source doit identifier le rapport annuel ou le dépôt
réglementaire utilisé.

L’import automatique essaie un snapshot annuel complet à la fois : Yahoo
Finance en premier, SEC EDGAR pour les sociétés qui y déposent leurs comptes,
puis ESEF/filings.xbrl.org pour les entreprises européennes disposant d’un
ISIN ou d’un LEI. Les rapprochements ISIN–LEI proviennent de GLEIF. La source
réellement retenue est enregistrée, les montants sont convertis en millions et
le même moteur d’analyse est appliqué que pour le formulaire manuel. Toutes
ces sources sont gratuites ; aucun fournisseur payant n’est requis. Les
détails et limites figurent dans
[`docs/public-data-sources.md`](docs/public-data-sources.md).

Pour arrêter :

```bash
docker compose down
```

Les données PostgreSQL sont conservées dans le volume `postgres_data`.

## Déploiement sur un VPS

La configuration de production est séparée du Compose local. Elle utilise
Caddy pour HTTPS automatique, des réseaux Docker privés, des secrets montés
comme fichiers, une migration Alembic contrôlée et des contrôles de santé
distincts pour le processus API et PostgreSQL.

Le guide complet de préparation, déploiement, sauvegarde et retour arrière est
disponible dans [`docs/deployment-vps.md`](docs/deployment-vps.md).

## Développement local

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
pytest
ruff check .
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Vite transmet automatiquement les requêtes `/api` au backend local sur le
port 8000.

## Structure

```text
backend/        API, domaine financier, persistance et migrations
frontend/       interface React
docs/           architecture, règles métier et spécification visuelle
.github/        intégration continue
docker-compose.yml
```

## API financière

```text
POST /api/v1/companies/{company_id}/financials
POST /api/v1/companies/{company_id}/financials/automatic
GET  /api/v1/companies/{company_id}/financials
POST /api/v1/companies/{company_id}/valuations
GET  /api/v1/companies/{company_id}/valuations
POST /api/v1/companies/{company_id}/scores
GET  /api/v1/companies/{company_id}/scores
GET  /api/v1/dashboard
POST /api/v1/ai/analyses
GET  /api/v1/indices
GET  /api/v1/indices/{code}
POST /api/v1/indices/companies/bulk
PATCH /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/archive
POST /api/v1/companies/{company_id}/restore
DELETE /api/v1/companies/{company_id}
```

## Comptes personnels

```text
POST /api/v1/auth/register
POST /api/v1/auth/resend-verification
POST /api/v1/auth/verify-email
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
POST /api/v1/auth/login
POST /api/v1/auth/mfa/verify
POST /api/v1/auth/mfa/setup
POST /api/v1/auth/mfa/confirm
POST /api/v1/auth/mfa/disable
GET  /api/v1/auth/me
GET  /api/v1/auth/sessions
DELETE /api/v1/auth/sessions/{session_id}
POST /api/v1/auth/sessions/revoke-other
POST /api/v1/auth/logout
```

Les sessions restent côté serveur et le navigateur reçoit un cookie
`HttpOnly`. Toutes les entreprises, analyses financières, valorisations,
scorings, données du dashboard et comparaisons IA sont isolés par
propriétaire. Un identifiant appartenant à un autre compte est traité comme
inconnu. La configuration, la migration du premier compte et les garanties de
sécurité sont détaillées dans
[`docs/authentication.md`](docs/authentication.md).

Les routes d’import valident les données, refusent un second import pour le
même exercice, historisent le snapshot, calculent les ratios et scores, puis
passent l’entreprise à l’état `ready`. La route de lecture restitue les
exercices du plus récent au plus ancien et leurs tendances.

## Financial Engine

Le moteur v0.4 calcule le Free Cash Flow, sa marge, le ROE, un ROIC avant impôt,
la couverture des intérêts et la dette nette. Il complète le MK Score par un
score de qualité et un score de sécurité, puis calcule les taux de croissance
annualisés lorsque deux exercices comparables sont disponibles.

Les formules, conventions et limites sont détaillées dans
[`docs/financial-engine.md`](docs/financial-engine.md).

## Valuation Engine

Le moteur v0.5 rattache chaque scénario à un snapshot financier précis. Il
calcule cinq estimations de la valeur totale des capitaux propres, retient la
médiane des valeurs positives comme estimation centrale, applique une marge de
sécurité configurable et mesure l’écart avec la capitalisation saisie.

Chaque résultat conserve ses hypothèses, sa formule, sa catégorie et une note
d’interprétation. Les formules, approximations et sources méthodologiques sont
détaillées dans [`docs/valuation-engine.md`](docs/valuation-engine.md).

## Scoring Engine

Le moteur v0.6 consolide, à poids égaux, le MK Quality Score, le MK Safety
Score, l’écart entre valeur centrale et capitalisation, et quatre signaux
quantitatifs servant de proxy de moat. Le résultat conserve la formule, le
poids, la contribution et une explication pour chaque composante.

Le signal final indique une priorité de recherche — « Profil favorable »,
« À approfondir » ou « Prudence » — et ne constitue pas une recommandation
d’achat. Les seuils, limites et références sont détaillés dans
[`docs/scoring-engine.md`](docs/scoring-engine.md).

## Dashboard

Le dashboard v0.7 agrège le dernier scoring disponible de chaque entreprise.
Il présente la distribution des signaux, classe les entreprises scorées par
score global décroissant et expose pour chacune l’écart de valeur ainsi que la
composante à approfondir.

Le « portefeuille de recherche » désigne l’univers comparatif de MK-VIP. Il ne
représente ni des positions détenues ni une recommandation : aucune quantité,
allocation, performance ou prix de revient n’est inventé. Le contrat API et
les règles de présentation sont détaillés dans
[`docs/dashboard.md`](docs/dashboard.md).

## Analyste IA

La v0.8 ajoute un assistant de recherche en trois modes : synthèse d’un
dossier, comparaison de deux entreprises et question en langage naturel.
L’API envoie au modèle uniquement les derniers snapshots, valorisations et
scorings déjà calculés par MK-VIP. Chaque constat doit citer un identifiant de
source interne valide.

Le fournisseur utilise l’API Responses d’OpenAI avec une sortie JSON stricte.
La clé reste dans `.env.local`, fichier ignoré par Git ; Docker Compose le
charge automatiquement lorsqu’il existe. Le modèle est configurable avec
`MKVIP_OPENAI_MODEL`.

L’assistant ne consulte pas le Web, ne remplace pas les calculs traçables et
ne formule aucune recommandation d’achat, de vente ou d’allocation. Le contrat
et ses garde-fous sont détaillés dans
[`docs/ai-analyst.md`](docs/ai-analyst.md).

## Source publique et limites

Le connecteur s’appuie sur `yfinance`, un projet open source non affilié à
Yahoo. Il utilise les API publiquement accessibles de Yahoo Finance sans clé.
Ces données sont destinées à la recherche et à un usage personnel ; leurs
conditions d’utilisation doivent être respectées.

MK-VIP conserve la source de chaque snapshot. Avant toute décision
d’investissement, les chiffres importés doivent être rapprochés du rapport
annuel audité ou du dépôt réglementaire de l’émetteur. Le formulaire manuel
reste disponible lorsqu’un champ public est absent ou doit être corrigé.

## Limites actuelles

Les analyses IA sont produites à la demande et ne sont pas historisées comme
des dossiers permanents. Les réponses identiques sont toutefois conservées
temporairement dans un cache isolé par utilisateur. La limitation des
connexions de la v0.11 est partagée par PostgreSQL entre les instances de
l’application ; une protection complémentaire en périphérie, avec pare-feu
applicatif et limitation réseau, reste recommandée avant une exploitation
publique à grande échelle.

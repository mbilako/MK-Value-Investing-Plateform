# MK Value Investing Platform

MK-VIP est une plateforme d’analyse fondamentale destinée à transformer des
données financières auditées en décisions d’investissement explicables.

La plateforme dispose maintenant d’un premier flux d’analyse exécutable :

- API Python/FastAPI ;
- PostgreSQL et migrations Alembic ;
- interface React/TypeScript ;
- import des entreprises et de leurs données financières annuelles ;
- import automatique du dernier exercice public via Yahoo Finance ;
- calcul de dix ratios, six indicateurs et trois scores explicables ;
- valorisation par DCF, Owner Earnings, EPV, Graham et multiple de résultat ;
- scoring global qualité, sécurité, valeur et moat quantitatif ;
- tableau de décision, distribution des signaux et portefeuille de recherche ;
- recherche des entreprises par nom ou ticker ;
- Analyste IA sourcé pour synthétiser, comparer et interroger les dossiers ;
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

Le parcours applicatif se déroule en deux temps :

1. importer une entreprise ;
2. utiliser « Ajouter les données », puis choisir l’import public automatique
   ou la saisie manuelle d’un exercice financier normalisé ;
3. ouvrir l’analyse d’une entreprise prête pour consulter ses scores,
   indicateurs et tendances historiques ;
4. préparer une valorisation, ajuster les hypothèses et comparer les cinq
   méthodes à la capitalisation observée ;
5. calculer le scoring global et lire les quatre contributions et explications.
6. revenir au tableau de décision pour comparer les derniers scorings, filtrer
   les signaux et rouvrir un dossier prioritaire.
7. ouvrir « Interroger l’IA » pour produire une synthèse, comparer deux
   entreprises ou poser une question sur les analyses MK-VIP disponibles.

Les montants du formulaire sont exprimés en millions dans la devise de
l’entreprise. La source doit identifier le rapport annuel ou le dépôt
réglementaire utilisé.

L’import automatique utilise le ticker Yahoo Finance de l’entreprise
(`AI.PA` pour Air Liquide), sélectionne le dernier exercice commun aux trois
états financiers, convertit les montants en millions puis applique exactement
le même moteur d’analyse que le formulaire manuel.

Pour arrêter :

```bash
docker compose down
```

Les données PostgreSQL sont conservées dans le volume `postgres_data`.

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
```

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

Les analyses IA sont produites à la demande et ne sont pas encore historisées.
L’authentification, les quotas par utilisateur et la mise en cache restent à
ajouter avant une exploitation multi-utilisateur.

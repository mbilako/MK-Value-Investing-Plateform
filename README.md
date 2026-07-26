# MK Value Investing Platform

MK-VIP est une plateforme d’analyse fondamentale destinée à transformer des
données financières auditées en décisions d’investissement explicables.

La plateforme dispose maintenant d’un premier flux d’analyse exécutable :

- API Python/FastAPI ;
- PostgreSQL et migrations Alembic ;
- interface React/TypeScript ;
- import des entreprises et de leurs données financières annuelles ;
- import automatique du dernier exercice public via Yahoo Finance ;
- calcul automatique de dix ratios et du MK Score ;
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
   ou la saisie manuelle d’un exercice financier normalisé.

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
```

Les deux routes valident les données, refusent un second import pour le même
exercice, historisent le snapshot, calculent les dix ratios et passent
l’entreprise à l’état `ready`.

## Source publique et limites

Le connecteur s’appuie sur `yfinance`, un projet open source non affilié à
Yahoo. Il utilise les API publiquement accessibles de Yahoo Finance sans clé.
Ces données sont destinées à la recherche et à un usage personnel ; leurs
conditions d’utilisation doivent être respectées.

MK-VIP conserve la source de chaque snapshot. Avant toute décision
d’investissement, les chiffres importés doivent être rapprochés du rapport
annuel audité ou du dépôt réglementaire de l’émetteur. Le formulaire manuel
reste disponible lorsqu’un champ public est absent ou doit être corrigé.

## Prochain incrément

Le prochain incrément développera le Financial Engine : Free Cash Flow, ROE,
ROIC, croissance pluriannuelle et premiers scores spécialisés, tout en
conservant le contrat normalisé comme frontière avec les fournisseurs.

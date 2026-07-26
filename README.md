# MK Value Investing Platform

MK-VIP est une plateforme d’analyse fondamentale destinée à transformer des
données financières auditées en décisions d’investissement explicables.

La plateforme dispose maintenant d’un premier flux d’analyse exécutable :

- API Python/FastAPI ;
- PostgreSQL et migrations Alembic ;
- interface React/TypeScript ;
- import des entreprises et de leurs données financières annuelles ;
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
2. utiliser « Ajouter les données » pour saisir un exercice financier
   normalisé et calculer son MK Score.

Les montants du formulaire sont exprimés en millions dans la devise de
l’entreprise. La source doit identifier le rapport annuel ou le dépôt
réglementaire utilisé.

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
```

Cette route valide les données, refuse un second import pour le même exercice,
historise le snapshot, calcule les dix ratios et passe l’entreprise à l’état
`ready`.

## Prochain incrément

Le prochain incrément ajoutera l’interface commune `FinancialDataProvider` et
un premier connecteur de données publiques. Le contrat normalisé actuel
restera la frontière entre les fournisseurs et le moteur d’analyse.

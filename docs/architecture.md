# Architecture v0.2 Financials

MK-VIP est organisé en monorepo afin de garder le domaine financier, l’API,
l’interface et l’exploitation versionnés ensemble.

## Backend

Le backend suit une architecture en couches :

- `api/` expose les routes FastAPI ;
- `schemas/` définit les contrats d’entrée et de sortie ;
- `analysis/` contient les règles financières indépendantes de toute source ;
- `repositories/` isole la persistance derrière une interface ;
- `models/` et `db/` implémentent PostgreSQL avec SQLAlchemy ;
- `core/` centralise la configuration.

Cette séparation permettra d’ajouter plusieurs fournisseurs de données sans
coupler le moteur d’analyse à Yahoo Finance, Euronext ou à une autre source.

## Frontend

Le frontend React est découpé par responsabilité :

- coque et navigation ;
- résumé du portefeuille d’entreprises ;
- univers d’investissement sous forme de tableau ;
- pipeline d’analyse ;
- tiroir d’import d’entreprise ;
- client API typé.

## Flux initial

1. L’utilisateur importe une entreprise.
2. L’API normalise le ticker et refuse les doublons.
3. PostgreSQL conserve l’entreprise avec le statut `pending`.
4. L’interface ajoute immédiatement la société à l’univers.
5. Les prochaines versions brancheront le fournisseur de données et feront
   progresser l’entreprise dans le pipeline.

## Flux financier normalisé

1. L’utilisateur choisit une entreprise au statut `pending`.
2. Le formulaire collecte un exercice, une source et les agrégats financiers.
3. Pydantic contrôle les devises, les valeurs positives et les dénominateurs.
4. Le moteur calcule dix ratios indépendamment du fournisseur de données.
5. Chaque ratio est évalué par le catalogue de règles versionné.
6. Le MK Score correspond au pourcentage de règles favorables.
7. Le snapshot, les ratios et le score sont historisés dans PostgreSQL.
8. L’entreprise passe au statut `ready`.

La contrainte `(company_id, fiscal_year)` garantit un seul snapshot par
entreprise et par exercice. Une future interface `FinancialDataProvider`
produira exactement le même contrat d’entrée que le formulaire actuel.

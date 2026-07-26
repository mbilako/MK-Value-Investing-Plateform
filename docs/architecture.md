# Architecture v0.4 Financial Engine

MK-VIP est organisé en monorepo afin de garder le domaine financier, l’API,
l’interface et l’exploitation versionnés ensemble.

## Backend

Le backend suit une architecture en couches :

- `api/` expose les routes FastAPI ;
- `schemas/` définit les contrats d’entrée et de sortie ;
- `analysis/` contient les règles financières indépendantes de toute source ;
- `providers/` expose `FinancialDataProvider`, le connecteur Yahoo et la
  normalisation des données publiques ;
- `repositories/` isole la persistance derrière une interface ;
- `models/` et `db/` implémentent PostgreSQL avec SQLAlchemy ;
- `core/` centralise la configuration.

Cette séparation permet d’ajouter plusieurs fournisseurs de données sans
coupler le moteur d’analyse à Yahoo Finance, Euronext ou à une autre source.

## Frontend

Le frontend React est découpé par responsabilité :

- coque et navigation ;
- résumé du portefeuille d’entreprises ;
- univers d’investissement sous forme de tableau ;
- pipeline d’analyse ;
- tiroir d’import d’entreprise ;
- client API typé.

Le tiroir d’analyse charge l’historique d’une entreprise à la demande. Il
présente séparément les scores, les indicateurs du dernier exercice et les
tendances calculées, sans transformer ces résultats en recommandation.

## Flux initial

1. L’utilisateur importe une entreprise.
2. L’API normalise le ticker et refuse les doublons.
3. PostgreSQL conserve l’entreprise avec le statut `pending`.
4. L’interface ajoute immédiatement la société à l’univers.
5. L’utilisateur peut déclencher l’import public depuis le tiroir financier.
6. Le fournisseur Yahoo récupère et normalise le dernier exercice complet.
7. L’analyse est historisée et l’entreprise progresse dans le pipeline.

## Flux financier normalisé

1. L’utilisateur choisit une entreprise au statut `pending`.
2. Le formulaire collecte un exercice, une source et les agrégats financiers.
3. Pydantic contrôle les devises, les valeurs positives et les dénominateurs.
4. Le moteur calcule dix ratios indépendamment du fournisseur de données.
5. Chaque ratio est évalué par le catalogue de règles versionné.
6. Le MK Score correspond au pourcentage de règles favorables.
7. Le snapshot, les ratios et le score sont historisés dans PostgreSQL.
8. L’entreprise passe au statut `ready`.

## Financial Engine

Le moteur enrichit chaque snapshot avec six indicateurs indépendants des
fournisseurs et trois scores explicables. Le dépôt expose aussi tous les
exercices d’une entreprise afin que le domaine calcule les CAGR sans logique
financière dans l’API ou l’interface.

Les valeurs normalisées, indicateurs et scores sont persistés ensemble. Les
tendances sont calculées à la lecture pour refléter l’historique disponible.

La contrainte `(company_id, fiscal_year)` garantit un seul snapshot par
entreprise et par exercice.

## Frontière fournisseur

`FinancialDataProvider` définit cinq capacités :

- rechercher une entreprise ;
- charger son profil ;
- charger les comptes de résultat annuels ;
- charger les bilans et flux de trésorerie annuels ;
- charger l’historique des prix.

`YahooFinanceProvider` traduit les libellés Yahoo vers les objets financiers
canoniques. `load_latest_snapshot` sélectionne le dernier exercice commun,
convertit les montants bruts en millions et produit un
`FinancialSnapshotCreate`. À partir de ce point, l’import manuel et l’import
automatique empruntent le même moteur de ratios et la même persistance.

Les erreurs réseau, les champs manquants et l’absence d’exercice commun sont
convertis en réponses API explicites. Aucun appel réseau n’est effectué dans
le moteur d’analyse lui-même.

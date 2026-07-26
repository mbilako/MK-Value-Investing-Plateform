# Architecture v0.6 Scoring Engine

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
tendances calculées. Il charge en parallèle les valorisations et les scorings,
permet de créer un scénario puis une synthèse multicritère sans transformer
ces résultats en recommandation.

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

## Valuation Engine

Le domaine `analysis/valuation.py` reçoit un snapshot financier normalisé et un
jeu d’hypothèses validé. Il calcule cinq méthodes sans dépendre de l’API, de la
base de données ou d’un fournisseur externe.

Une valorisation référence explicitement son entreprise et son snapshot. La
table `valuation_analyses` conserve l’exercice, la devise, la capitalisation,
les hypothèses, le détail des méthodes, l’estimation centrale, la valeur après
marge de sécurité et l’écart de marché. Plusieurs scénarios peuvent ainsi
coexister pour un même exercice.

Le flux est le suivant :

1. Le tiroir charge en parallèle l’historique financier et les valorisations.
2. L’utilisateur ajuste les hypothèses du dernier exercice.
3. Pydantic contrôle notamment que le taux d’actualisation dépasse la
   croissance terminale.
4. Le domaine calcule les cinq méthodes et la médiane des valeurs utilisables.
5. Le dépôt persiste le scénario complet.
6. L’interface présente l’estimation centrale puis les formules et limites de
   chaque méthode.

## Scoring Engine

Le domaine `analysis/scoring.py` reçoit le snapshot financier analysé et une
valorisation calculable du même exercice. Il agrège quatre composantes à poids
égaux : qualité, sécurité, valeur et moat quantitatif.

La table `scoring_analyses` référence explicitement l’entreprise, le snapshot
et le scénario de valorisation. Elle conserve les composantes, leurs formules,
leurs contributions, les explications et le signal final. Un recalcul crée un
nouvel enregistrement afin de préserver la traçabilité.

Le flux est le suivant :

1. Le tiroir charge les snapshots, valorisations et scorings en parallèle.
2. L’utilisateur déclenche le calcul sur le dernier exercice.
3. L’API vérifie qu’un snapshot et une valorisation calculable existent pour
   cet exercice.
4. Le domaine calcule les quatre composantes, le score pondéré et le signal.
5. Le dépôt persiste le résultat complet avec ses références.
6. L’interface affiche le score global, les contributions et quatre
   explications lisibles.

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

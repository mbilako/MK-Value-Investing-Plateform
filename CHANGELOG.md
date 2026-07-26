# Changelog

## 0.3.0 - 2026-07-26

### Added

- Interface commune `FinancialDataProvider` pour découpler les sources du
  moteur d’analyse.
- Premier connecteur Yahoo Finance sans clé API.
- Recherche d’entreprises, profils, états annuels et historique de prix
  normalisés par le fournisseur Yahoo.
- Import automatique du dernier exercice annuel complet depuis le tableau de
  bord.
- Messages d’erreur lisibles lorsque la source est indisponible ou incomplète.

### Changed

- Le client API restitue désormais le détail des erreurs du backend.
- L’import manuel reste disponible comme solution de contrôle et de repli.

## 0.2.0 - 2026-07-25

### Added

- Import de snapshots financiers annuels normalisés.
- Calcul automatique de dix ratios et du MK Score.
- Historisation PostgreSQL avec unicité par entreprise et exercice.
- Parcours d’interface « Ajouter les données » pour les entreprises en attente.
- Affichage du statut d’analyse et du MK Score dans l’univers d’investissement.

## 0.1.0 - 2026-07-25

### Added

- Socle monorepo de MK-VIP.
- API FastAPI de santé et de gestion des entreprises.
- Modèle PostgreSQL et première migration Alembic.
- Catalogue initial de règles d’investissement issu du classeur métier.
- Tableau de bord React responsive et parcours d’import d’Air Liquide.
- Tests automatisés backend et frontend.
- Docker Compose et intégration continue GitHub Actions.

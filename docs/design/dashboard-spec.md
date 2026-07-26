# MK-VIP dashboard — visual specification

## Product surface

The first implemented surface is the real application dashboard, not a
marketing page. It has six component regions:

1. `AppShell`
2. `Sidebar`
3. `Header`
4. `SummaryStrip`
5. `CompanyUniverse`
6. `AnalysisPipeline`

The import interaction uses a right-side drawer with a simple company form.

## Copy lock

- MK-VIP
- Vue d’ensemble
- Entreprises
- Analyses
- Règles
- Journal
- Données prêtes
- Importer une entreprise
- Univers d’investissement
- Rechercher une entreprise ou un ticker
- Aucune entreprise importée
- Commencer avec Air Liquide
- Moteur d’analyse
- Import
- Validation
- Normalisation
- Ratios
- MK Score
- API opérationnelle · PostgreSQL connecté

## Design tokens

- Canvas: `#ffffff`
- Subtle canvas: `#f7f9fb`
- Navy: `#10223f`
- Muted text: `#637083`
- Border: `#d9e0e8`
- Emerald: `#087a57`
- Emerald tint: `#e9f5f0`
- Danger: `#b42318`
- Radius: 8px for controls, 10px for functional panels
- Shadow: only the import drawer
- Typography: Inter-like sans-serif for UI, Georgia-like serif for large
  section headings

## Container and responsive rules

- Desktop uses a 256px navigation rail and an open content canvas.
- Summary metrics form one bordered strip, not separate cards.
- The company universe is table-driven.
- At widths below 800px, the rail becomes a compact top navigation and the
  drawer fills the viewport.
- No gradients, decorative charts, badges, glows, or invented financial data.

## Intentional functional additions

- `Version 0.2 Financials` identifies the implemented milestone in the
  navigation footer.
- `Importez votre première entreprise pour lancer l’analyse.` explains the
  empty state without inventing product data.
- The import-drawer concept is used only for the drawer anatomy. The dashboard
  concept remains authoritative for the content visible behind the drawer.
- `Ajouter les données`, `Importer les données financières`,
  `Importer automatiquement avec Yahoo Finance`, `Calculer le MK Score` and
  the ready-state score are the intentional v0.3
  additions that complete the financial-analysis workflow.

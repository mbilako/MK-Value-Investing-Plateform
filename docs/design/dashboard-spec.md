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

## v0.4 analysis drawer

- Clicking a ready company opens a right-side financial analysis drawer.
- The first level shows MK, quality and safety scores.
- The second level shows the six latest indicators and available CAGR trends.
- Source, fiscal year and a non-recommendation notice remain visible.
- With a single exercise, one concise insufficient-history message replaces
  empty or invented charts.
- Below 800px, the drawer occupies the full viewport width.

## v0.5 valuation workflow

- The existing analysis drawer gains one `Valorisation` section after trends.
- A single secondary action reveals the assumptions instead of presenting a
  second competing drawer.
- The result starts with central estimate, safety value and market gap, then
  lists the five methods with their formula and limitation.
- Percentage fields show their unit beside the value and remain fully labelled.
- The navy, emerald, border, radius and typography tokens remain unchanged.
- Below 800px, summaries, methods and assumptions collapse to one column
  without horizontal scrolling.

## v0.6 scoring workflow

- The analysis drawer gains one `Scoring global` section after valuation.
- The first level pairs the 0–100 score with one plain-language research
  signal; neither is presented as a buy recommendation.
- Four equal-weight component cards expose score, progress, contribution and
  a concise methodological note.
- Four icon-led insight rows explain quality, safety, valuation and the moat
  proxy without decorative charts.
- The calculation action uses the valuation from the same fiscal year and can
  be rerun while preserving prior records.
- Below 700px, summary and component grids collapse to one column without
  horizontal scrolling.

## v0.7 decision dashboard

- A `Tableau de décision` section precedes the complete investment universe.
- Signal distribution uses one compact stacked bar and an explicit legend;
  colour never carries meaning alone.
- The research portfolio remains table-driven and shows company, global score,
  signal, valuation gap, weakest component and one analysis action.
- `Portefeuille de recherche` means a comparison universe, not actual
  holdings. No quantity, allocation, cost basis, gain or loss is inferred.
- The signal filter updates the research table locally. The universe search
  matches both company name and ticker.
- At narrower widths, distribution and research table stack; wide tabular
  content scrolls horizontally without clipping actions.

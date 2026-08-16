import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type {
  Company,
  FinancialAnalysis,
  FinancialHistory,
} from "../api/client";
import { AnalysisDrawer } from "./AnalysisDrawer";

const company: Company = {
  id: "bank-1",
  name: "BNP Paribas",
  ticker: "BNP.PA",
  exchange: "Euronext Paris",
  country: "France",
  currency: "EUR",
  isin: "FR0000131104",
  cik: null,
  lei: null,
  provider_symbols: {},
  index_memberships: ["CAC40"],
  archived_at: null,
  status: "ready",
  latest_mk_score: null,
  latest_quality_score: null,
  latest_safety_score: null,
};

const analysis: FinancialAnalysis = {
  id: "analysis-1",
  company_id: company.id,
  fiscal_year: 2025,
  source: "Yahoo Finance · BNP.PA · exercice 2025",
  currency: "EUR",
  analysis_profile: "financial",
  revenue: 68_804,
  ebitda: null,
  depreciation_amortization: 2_367,
  ebit: 16_296,
  interest_expense: 50_329,
  operating_cash_flow: 46_571,
  capex: 2_875,
  net_income: 12_225,
  pretax_income: 15_200,
  market_cap: 120_000,
  closing_price: 82.4,
  shares_outstanding: 1_150,
  treasury_stock_value: 1_200,
  total_assets: 2_792_981,
  current_assets: null,
  current_liabilities: null,
  financial_debt: 398_488,
  cash: 326_959,
  total_equity: 132_173,
  investing_cash_flow: -18_500,
  metrics: [],
  indicators: [
    {
      key: "reported_revenue",
      label: "Revenus publiés / produit d'exploitation",
      value: 68_804,
      unit: "EUR",
      formula: "Poste de revenus publié par l'émetteur",
    },
  ],
  mk_score: null,
  quality_score: null,
  safety_score: null,
  created_at: "2026-08-02T00:00:00Z",
};

const history: FinancialHistory = {
  company_id: company.id,
  snapshots: [analysis],
  trend: {
    periods: 1,
    first_year: 2025,
    last_year: 2025,
    revenue_cagr: null,
    net_income_cagr: null,
    free_cash_flow_cagr: null,
  },
};

describe("AnalysisDrawer financial institutions", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("uses the same movable fundamental layout for every sector", () => {
    render(
      <AnalysisDrawer
        company={company}
        history={history}
        valuations={[]}
        scores={[]}
        loading={false}
        error={null}
        onCreateValuation={async () => {
          throw new Error("not expected");
        }}
        onCreateScore={async () => {
          throw new Error("not expected");
        }}
        onClose={() => undefined}
      />,
    );

    expect(screen.queryByText("Profil banque ou assurance")).not.toBeInTheDocument();
    expect(screen.getByText("Revenus publiés")).toBeInTheDocument();
    expect(screen.getAllByText("EBITDA")).toHaveLength(2);
    expect(screen.getByText("Total actif")).toBeInTheDocument();
    expect(screen.queryByText("Actions en circulation")).not.toBeInTheDocument();
    expect(screen.getByText("Flux de trésorerie d’investissement")).toBeInTheDocument();
    expect(screen.getByText("Dernier cours de bourse au 31 décembre")).toBeInTheDocument();
    expect(
      screen.getByText("Valeur économique des capitaux propres par action"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "(Capitaux propres + actions autodétenues) / actions en circulation",
      ),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Voir les ratios détaillés du dernier exercice")).not.toBeInTheDocument();

    const cardsBefore = document.querySelectorAll(
      ".indicator-grid--fundamentals .indicator-card",
    );
    expect(cardsBefore[0]).toHaveTextContent("Revenus publiés");
    expect(cardsBefore[1]).toHaveTextContent("Résultat net");
    expect(cardsBefore[10]).toHaveTextContent("Actif circulant");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Déplacer Revenus publiés vers la droite",
      }),
    );

    const cardsAfter = document.querySelectorAll(
      ".indicator-grid--fundamentals .indicator-card",
    );
    expect(cardsAfter[0]).toHaveTextContent("Résultat net");
    expect(cardsAfter[1]).toHaveTextContent("Revenus publiés");
  });

  it("compares the last two fiscal years and adds the requested ratios to history", () => {
    const latest: FinancialAnalysis = {
      ...analysis,
      id: "analysis-latest",
      analysis_profile: "standard",
      revenue: 1_000,
      ebitda: 350,
      ebit: 200,
      interest_expense: 20,
      net_income: 250,
      pretax_income: 160,
      market_cap: 800,
      current_assets: 1_000,
      current_liabilities: 400,
      financial_debt: 500,
      cash: 100,
      total_assets: 1_000,
      total_equity: 400,
      treasury_stock_value: 100,
    };
    const previous: FinancialAnalysis = {
      ...latest,
      id: "analysis-previous",
      fiscal_year: 2024,
      revenue: 800,
      ebitda: 320,
      ebit: 160,
      interest_expense: 32,
      net_income: 80,
      pretax_income: 100,
      market_cap: 1_000,
      current_assets: 800,
      current_liabilities: 500,
      financial_debt: 600,
      cash: 100,
      total_assets: 900,
    };
    const twoYearHistory: FinancialHistory = {
      ...history,
      snapshots: [latest, previous],
      trend: {
        ...history.trend,
        periods: 2,
        first_year: 2024,
      },
    };

    render(
      <AnalysisDrawer
        company={company}
        history={twoYearHistory}
        valuations={[]}
        scores={[]}
        loading={false}
        error={null}
        onCreateValuation={async () => {
          throw new Error("not expected");
        }}
        onCreateScore={async () => {
          throw new Error("not expected");
        }}
        onClose={() => undefined}
      />,
    );

    expect(screen.queryByRole("heading", { name: "Tendance annualisée" })).not.toBeInTheDocument();
    const comparison = screen
      .getByRole("heading", { name: "Comparaison des deux derniers exercices" })
      .closest("section");
    expect(comparison).not.toBeNull();
    const comparisonView = within(comparison as HTMLElement);
    expect(comparisonView.getByText("2025 vs 2024")).toBeInTheDocument();
    expect(comparisonView.getByText("Évolution : +25 %")).toBeInTheDocument();

    const favorablePe = comparisonView.getByText("3,2×").closest("strong");
    expect(favorablePe).toHaveClass("comparison-value--favorable");
    expect(comparisonView.getByText("2024 : 12,5×")).toBeInTheDocument();
    const favorableCurrentRatio = comparisonView.getByText("2,5×").closest("strong");
    expect(favorableCurrentRatio).toHaveClass("comparison-value--favorable");
    expect(comparisonView.getByText("2024 : 1,6×")).toBeInTheDocument();
    const favorableMarketCapToAssets = comparisonView.getByText("0,8×").closest("strong");
    expect(favorableMarketCapToAssets).toHaveClass("comparison-value--favorable");
    expect(comparisonView.getByText("2024 : 1,11×")).toBeInTheDocument();
    expect(comparisonView.getByText("Current ratio")).toBeInTheDocument();
    expect(
      comparisonView.getByText("Capitalisation boursière / total actif"),
    ).toBeInTheDocument();
    const unfavorableMargin = comparisonView.getByText("35 %").closest("strong");
    expect(unfavorableMargin).toHaveClass("comparison-value--unfavorable");
    const favorableNetMargin = comparisonView.getByText("25 %").closest("strong");
    expect(favorableNetMargin).toHaveClass("comparison-value--favorable");
    const stockBondYieldCard = comparisonView
      .getByText("Rendement de l’action-obligation")
      .closest("article");
    expect(stockBondYieldCard).not.toBeNull();
    expect(stockBondYieldCard).toHaveAttribute(
      "title",
      "Résultat avant impôt / capitalisation boursière totale",
    );
    expect(within(stockBondYieldCard as HTMLElement).getByText("20 %")).toBeInTheDocument();
    expect(
      within(stockBondYieldCard as HTMLElement).getByText("2024 : 10 %"),
    ).toBeInTheDocument();
    const unfavorableLeverage = comparisonView.getByText("1,2×").closest("strong");
    expect(unfavorableLeverage).toHaveClass("comparison-value--unfavorable");
    expect(comparisonView.getByText("Effet de levier ajusté")).toBeInTheDocument();
    expect(comparisonView.getByText("Seuil vert : > 40 %")).toBeInTheDocument();
    expect(comparisonView.getByText("Seuil vert : > 20 %")).toBeInTheDocument();
    expect(comparisonView.getByText("Seuil vert : < 20×")).toBeInTheDocument();
    expect(comparisonView.getByText("Seuil vert : > 2×")).toBeInTheDocument();
    expect(comparisonView.getByText("Seuil vert : < 1,5×")).toBeInTheDocument();

    const annualHistory = screen.getByRole("table", { name: "Historique fondamental" });
    expect(within(annualHistory).getByRole("columnheader", { name: /Marge brute/ })).toBeInTheDocument();
    expect(within(annualHistory).getByRole("columnheader", { name: /Marge nette/ })).toBeInTheDocument();
    expect(within(annualHistory).getByRole("columnheader", { name: /Poids dette financière/ })).toBeInTheDocument();
    expect(within(annualHistory).getByRole("columnheader", { name: /Décote/ })).toBeInTheDocument();
    expect(within(annualHistory).getByRole("columnheader", { name: /Rendement action-obligation/ })).toBeInTheDocument();
    expect(
      within(annualHistory).getByRole("columnheader", { name: /Effet de levier ajusté/ }),
    ).toBeInTheDocument();
    expect(within(annualHistory).getByRole("columnheader", { name: /Niveau d’endettement/ })).toBeInTheDocument();
    expect(
      within(annualHistory).getByText("35 %", {
        selector: ".comparison-value--unfavorable",
      }),
    ).toBeInTheDocument();
    expect(
      within(annualHistory).getByText("40 %", {
        selector: ".comparison-value--unfavorable",
      }),
    ).toBeInTheDocument();
    expect(
      within(annualHistory).getByText("25 %", {
        selector: ".comparison-value--favorable",
      }),
    ).toBeInTheDocument();
  });
});

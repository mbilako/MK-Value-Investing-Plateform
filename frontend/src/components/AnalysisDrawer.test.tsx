import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
  market_cap: 120_000,
  total_assets: 2_792_981,
  current_assets: null,
  current_liabilities: null,
  financial_debt: 398_488,
  cash: 326_959,
  total_equity: 132_173,
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
  it("shows public figures without an industrial score or valuation", () => {
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

    expect(screen.getByText("Profil banque ou assurance")).toBeInTheDocument();
    expect(
      screen.getByText("Revenus publiés / produit d'exploitation"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Quality Score")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Valorisation" }),
    ).not.toBeInTheDocument();
  });
});

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import type {
  CompanyClient,
  FinancialPayload,
} from "./api/client";

afterEach(cleanup);

const unusedAutomaticImport = async () => {
  throw new Error("Import automatique non utilisé dans ce scénario.");
};

const unusedFinancialHistory = async () => {
  throw new Error("Historique financier non utilisé dans ce scénario.");
};

const unusedValuations = async () => [];

const unusedCreateValuation = async () => {
  throw new Error("Valorisation non utilisée dans ce scénario.");
};

describe("MK-VIP dashboard", () => {
  it("shows the empty investment universe", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Aucune entreprise importée")).toBeInTheDocument();
    expect(screen.getByText("Import")).toBeInTheDocument();
    expect(screen.getByText("MK Score")).toBeInTheDocument();
    expect(screen.getByText("Version 0.5 Valuation Engine")).toBeInTheDocument();
  });

  it("opens the Air Liquide import form with normalized defaults", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(
      screen.getByRole("button", { name: "Commencer avec Air Liquide" }),
    );

    expect(
      screen.getByRole("heading", { name: "Importer une entreprise" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nom de l’entreprise")).toHaveValue(
      "Air Liquide",
    );
    expect(screen.getByLabelText("Ticker")).toHaveValue("AI.PA");
  });

  it("adds an imported company to the universe", async () => {
    const user = userEvent.setup();
    const client: CompanyClient = {
      listCompanies: async () => [],
      createCompany: async (payload) => ({
        id: "company-1",
        status: "pending",
        ...payload,
        ticker: payload.ticker.toUpperCase(),
        currency: payload.currency.toUpperCase(),
      }),
      importFinancials: async () => {
        throw new Error("Non utilisé dans ce scénario.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };
    render(<App client={client} />);

    await user.click(
      screen.getByRole("button", { name: "Commencer avec Air Liquide" }),
    );
    await user.click(screen.getByRole("button", { name: "Importer" }));

    expect(await screen.findByText("AI.PA")).toBeInTheDocument();
    expect(screen.getByText("Air Liquide")).toBeInTheDocument();
    expect(
      screen.queryByText("Aucune entreprise importée"),
    ).not.toBeInTheDocument();
  });

  it("opens the financial import for a pending company", async () => {
    const user = userEvent.setup();
    const client: CompanyClient = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending",
        },
      ],
      createCompany: async (payload) => ({
        id: "company-2",
        status: "pending",
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Non utilisé dans ce scénario.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Importer les données financières pour Air Liquide",
      }),
    );

    expect(
      screen.getByRole("heading", {
        name: "Importer les données financières",
      }),
    ).toBeInTheDocument();
  });

  it("restores the latest MK score when companies are loaded", async () => {
    const client: CompanyClient = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready",
          latest_mk_score: 72.5,
        },
      ],
      createCompany: async (payload) => ({
        id: "company-2",
        status: "pending",
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Non utilisé dans ce scénario.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };

    render(<App client={client} />);

    expect(await screen.findByText("MK Score 72.5")).toBeInTheDocument();
    expect(screen.getByLabelText("analyses : 1")).toBeInTheDocument();
  });

  it("submits normalized financials and displays the MK score", async () => {
    const user = userEvent.setup();
    let importedRevenue: number | undefined;
    let importedOperatingCashFlow: number | undefined;
    const client: CompanyClient = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending" as const,
        },
      ],
      createCompany: async (payload: Parameters<CompanyClient["createCompany"]>[0]) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async (
        _companyId: string,
        payload: FinancialPayload,
      ) => {
        importedRevenue = payload.revenue;
        importedOperatingCashFlow = payload.operating_cash_flow;
        return {
          ...payload,
          id: "analysis-1",
          company_id: "company-1",
          mk_score: 100,
          metrics: [],
          indicators: [],
          quality_score: 100,
          safety_score: 100,
          created_at: "2026-07-25T00:00:00Z",
        };
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Importer les données financières pour Air Liquide",
      }),
    );

    const fields: Array<[string, string]> = [
      ["Source", "Rapport annuel 2025"],
      ["Chiffre d’affaires", "1000"],
      ["EBITDA", "450"],
      ["Dotations aux amortissements", "20"],
      ["EBIT", "400"],
      ["Charges d’intérêts", "40"],
      ["Flux de trésorerie d’exploitation", "-25"],
      ["Investissements (Capex)", "40"],
      ["Résultat net", "250"],
      ["Capitalisation boursière", "4500"],
      ["Total actif", "4000"],
      ["Actif circulant", "600"],
      ["Passif exigible", "250"],
      ["Dette financière", "600"],
      ["Trésorerie", "100"],
      ["Capitaux propres", "1000"],
    ];
    for (const [label, value] of fields) {
      await user.type(screen.getByLabelText(label), value);
    }
    await user.click(
      screen.getByRole("button", { name: "Calculer le MK Score" }),
    );

    expect(importedRevenue).toBe(1000);
    expect(importedOperatingCashFlow).toBe(-25);
    expect(await screen.findByText("MK Score 100")).toBeInTheDocument();
    expect(screen.getByText("Analyse prête")).toBeInTheDocument();
    expect(screen.getByLabelText("analyses : 1")).toBeInTheDocument();
  });

  it("imports the latest public financial data automatically", async () => {
    const user = userEvent.setup();
    const client = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending" as const,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Le formulaire manuel ne doit pas être utilisé.");
      },
      importFinancialsAutomatically: async (companyId: string) => {
        if (companyId !== "company-1") {
          throw new Error("Mauvaise entreprise.");
        }
        return {
          id: "analysis-1",
          company_id: companyId,
          fiscal_year: 2025,
          source: "Yahoo Finance · AI.PA · exercice 2025",
          currency: "EUR",
          revenue: 1000,
          ebitda: 450,
          depreciation_amortization: 20,
          ebit: 400,
          interest_expense: 40,
          operating_cash_flow: 300,
          capex: 40,
          net_income: 250,
          market_cap: 4500,
          total_assets: 4000,
          current_assets: 600,
          current_liabilities: 250,
          financial_debt: 600,
          cash: 100,
          total_equity: 1000,
          mk_score: 80,
          metrics: [],
          indicators: [],
          quality_score: 75,
          safety_score: 100,
          created_at: "2026-07-26T00:00:00Z",
        };
      },
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Importer les données financières pour Air Liquide",
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Importer automatiquement avec Yahoo Finance",
      }),
    );

    expect(await screen.findByText("MK Score 80")).toBeInTheDocument();
    expect(screen.getByText("Analyse prête")).toBeInTheDocument();
  });

  it("opens the financial engine analysis for a ready company", async () => {
    const user = userEvent.setup();
    const client = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready" as const,
          latest_mk_score: 80,
          latest_quality_score: 75,
          latest_safety_score: 100,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 450,
            depreciation_amortization: 20,
            ebit: 400,
            interest_expense: 40,
            operating_cash_flow: 300,
            capex: 40,
            net_income: 250,
            market_cap: 4_500,
            total_assets: 4_000,
            current_assets: 600,
            current_liabilities: 250,
            financial_debt: 600,
            cash: 100,
            total_equity: 1_000,
            metrics: [],
            indicators: [
              {
                key: "free_cash_flow",
                label: "Free Cash Flow",
                value: 260,
                unit: "EUR",
                formula:
                  "Flux de trésorerie d’exploitation − investissements",
              },
              {
                key: "return_on_equity",
                label: "Rendement des capitaux propres (ROE)",
                value: 0.25,
                unit: "ratio",
                formula: "Résultat net / capitaux propres",
              },
            ],
            mk_score: 80,
            quality_score: 75,
            safety_score: 100,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
    };
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Voir l’analyse financière de Air Liquide",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Analyse financière" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Quality Score")).toBeInTheDocument();
    expect(screen.getByText("Safety Score")).toBeInTheDocument();
    expect(screen.getAllByText("Free Cash Flow").length).toBeGreaterThan(0);
    expect(screen.getByText("260 M EUR")).toBeInTheDocument();
    expect(screen.getByText("Historique insuffisant")).toBeInTheDocument();
  });

  it("creates an explainable valuation from the latest analysis", async () => {
    const user = userEvent.setup();
    let submittedGrowthRate: number | undefined;
    const client: CompanyClient = {
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready" as const,
          latest_mk_score: 80,
          latest_quality_score: 75,
          latest_safety_score: 100,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 300,
            depreciation_amortization: 40,
            ebit: 250,
            interest_expense: 20,
            operating_cash_flow: 180,
            capex: 80,
            net_income: 160,
            market_cap: 2_200,
            total_assets: 2_000,
            current_assets: 500,
            current_liabilities: 250,
            financial_debt: 400,
            cash: 100,
            total_equity: 800,
            metrics: [],
            indicators: [],
            mk_score: 80,
            quality_score: 75,
            safety_score: 100,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: async () => [],
      createValuation: async (
        companyId: string,
        payload: Parameters<CompanyClient["createValuation"]>[1],
      ) => {
        submittedGrowthRate = payload.assumptions.growth_rate;
        return {
          id: "valuation-1",
          company_id: companyId,
          financial_snapshot_id: "analysis-1",
          fiscal_year: payload.fiscal_year,
          currency: "EUR",
          market_cap: 2_200,
          assumptions: {
            growth_rate: 0.05,
            terminal_growth_rate: 0.02,
            cost_of_equity: 0.1,
            wacc: 0.08,
            tax_rate: 0.25,
            projection_years: 5,
            target_pe: 15,
            corporate_bond_yield: 0.044,
            margin_of_safety: 0.25,
          },
          methods: [
            {
              key: "dcf",
              label: "DCF des flux disponibles",
              value: 1_446.21,
              category: "proxy",
              formula: "Somme des FCF projetés actualisés",
              base_metric: "Free Cash Flow",
              note: "Proxy de flux aux actionnaires.",
            },
            {
              key: "buffett_owner_earnings",
              label: "Buffett Owner Earnings",
              value: 1_735.45,
              category: "proxy",
              formula: "Résultat net + amortissements − investissements",
              base_metric: "Owner Earnings",
              note: "Capex de maintenance approximé.",
            },
            {
              key: "earnings_power_value",
              label: "Earnings Power Value",
              value: 2_043.75,
              category: "intrinsic",
              formula: "NOPAT / WACC − dette + trésorerie",
              base_metric: "NOPAT",
              note: "Sans croissance future.",
            },
            {
              key: "graham",
              label: "Formule de Graham",
              value: 2_960,
              category: "proxy",
              formula: "Résultat net × (8,5 + 2g) × 4,4 / Y",
              base_metric: "Résultat net",
              note: "Raccourci historique.",
            },
            {
              key: "pe_multiple",
              label: "Multiple de résultat",
              value: 2_400,
              category: "relative",
              formula: "Résultat net × PER cible",
              base_metric: "Résultat net",
              note: "Prix relatif.",
            },
          ],
          central_estimate: 2_043.75,
          margin_of_safety_value: 1_532.81,
          market_gap: -0.071023,
          created_at: "2026-07-26T00:00:00Z",
        };
      },
    };
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Voir l’analyse financière de Air Liquide",
      }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Préparer une valorisation",
      }),
    );
    expect(
      screen.getByRole("heading", { name: "Hypothèses de valorisation" }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Estimer la valeur" }),
    );

    expect(submittedGrowthRate).toBe(0.05);
    expect(
      within(
        await screen.findByRole("article", {
          name: "Estimation centrale",
        }),
      ).getByText("2 043,75 M EUR"),
    ).toBeInTheDocument();
    expect(screen.getByText("DCF des flux disponibles")).toBeInTheDocument();
    expect(screen.getByText("Buffett Owner Earnings")).toBeInTheDocument();
    expect(screen.getByText("Earnings Power Value")).toBeInTheDocument();
    expect(screen.getByText("Formule de Graham")).toBeInTheDocument();
    expect(screen.getByText("Multiple de résultat")).toBeInTheDocument();
  });
});

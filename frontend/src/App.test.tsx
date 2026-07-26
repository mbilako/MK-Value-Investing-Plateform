import { cleanup, render, screen } from "@testing-library/react";
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

describe("MK-VIP dashboard", () => {
  it("shows the empty investment universe", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Aucune entreprise importée")).toBeInTheDocument();
    expect(screen.getByText("Import")).toBeInTheDocument();
    expect(screen.getByText("MK Score")).toBeInTheDocument();
    expect(screen.getByText("Version 0.3 Data Engine")).toBeInTheDocument();
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
    };

    render(<App client={client} />);

    expect(await screen.findByText("MK Score 72.5")).toBeInTheDocument();
    expect(screen.getByLabelText("analyses : 1")).toBeInTheDocument();
  });

  it("submits normalized financials and displays the MK score", async () => {
    const user = userEvent.setup();
    let importedRevenue: number | undefined;
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
        return {
          ...payload,
          id: "analysis-1",
          company_id: "company-1",
          mk_score: 100,
          metrics: [],
          created_at: "2026-07-25T00:00:00Z",
        };
      },
      importFinancialsAutomatically: unusedAutomaticImport,
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
          created_at: "2026-07-26T00:00:00Z",
        };
      },
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
});

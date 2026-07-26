import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import type {
  CompanyClient,
  FinancialPayload,
} from "./api/client";

afterEach(cleanup);

describe("MK-VIP dashboard", () => {
  it("shows the empty investment universe", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Aucune entreprise importée")).toBeInTheDocument();
    expect(screen.getByText("Import")).toBeInTheDocument();
    expect(screen.getByText("MK Score")).toBeInTheDocument();
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
});

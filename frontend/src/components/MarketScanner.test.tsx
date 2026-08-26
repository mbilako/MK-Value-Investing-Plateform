import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MarketScan } from "../api/client";
import { MarketScanner } from "./MarketScanner";

const queuedScan: MarketScan = {
  id: "scan-1",
  status: "queued",
  criteria: {
    market: "US",
    index_code: null,
    country_code: null,
    exchanges: ["NASDAQ", "NYSE", "AMEX"],
    years: 5,
    minimum_decline_pct: 80,
    minimum_market_cap: null,
    ordinary_shares_only: true,
  },
  request_text: "Actions US en baisse de 80 % sur 5 ans",
  universe_source: "Nasdaq public screener",
  price_source: "Yahoo Finance",
  total_securities: 0,
  processed_securities: 0,
  matched_securities: 0,
  failed_securities: 0,
  insufficient_history_securities: 0,
  progress_pct: 0,
  error_message: null,
  created_at: "2026-08-26T10:00:00Z",
  started_at: null,
  completed_at: null,
  results: [],
};

afterEach(cleanup);

describe("MarketScanner", () => {
  it("starts a deterministic scan from a natural-language request", async () => {
    const user = userEvent.setup();
    const createFromQuestion = vi.fn().mockResolvedValue(queuedScan);
    const cancelScan = vi.fn().mockResolvedValue({
      ...queuedScan,
      status: "cancelled",
      completed_at: "2026-08-26T10:01:00Z",
    });
    const listScans = vi.fn().mockResolvedValue([]);
    render(
      <MarketScanner
        listIndices={vi.fn().mockResolvedValue([])}
        listNationalMarkets={vi.fn().mockResolvedValue([])}
        listScans={listScans}
        createFromQuestion={createFromQuestion}
        createScan={vi.fn()}
        getScan={vi.fn()}
        retryScan={vi.fn()}
        cancelScan={cancelScan}
        exportScan={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Scan des marchés nationaux et indices MK-VIP" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Lancer avec l’agent" }));

    expect(createFromQuestion).toHaveBeenCalledWith(
      "Trouve sur le marché américain les actions ayant baissé d’au moins 80 % sur 5 ans",
    );
    expect(await screen.findByText("En attente")).toBeInTheDocument();
    await user.click(screen.getByText("Critères manuels"));
    await user.clear(screen.getByRole("spinbutton", { name: "Baisse minimale" }));
    await user.type(screen.getByRole("spinbutton", { name: "Baisse minimale" }), "70");
    expect(screen.getByRole("textbox", { name: "Demande à l’agent" })).toHaveValue(
      "Trouve sur le marché américain les actions ayant baissé d’au moins 70 % sur 5 ans",
    );
    await user.click(screen.getByRole("button", { name: "Arrêter l’analyse" }));
    expect(cancelScan).toHaveBeenCalledWith("scan-1");
    expect(await screen.findByText("Arrêté")).toBeInTheDocument();
  });

  it("starts a scan for any selected MK-VIP index", async () => {
    const user = userEvent.setup();
    const createScan = vi.fn().mockResolvedValue({
      ...queuedScan,
      criteria: { ...queuedScan.criteria, market: "INDEX", index_code: "CAC40" },
    });
    render(
      <MarketScanner
        listIndices={vi.fn().mockResolvedValue([
          {
            code: "CAC40",
            name: "CAC 40",
            isin: null,
            market: "XPAR",
            provider: "Euronext",
            region: "Europe",
            country: "France",
            kind: "broad",
          },
        ])}
        listNationalMarkets={vi.fn().mockResolvedValue([])}
        listScans={vi.fn().mockResolvedValue([])}
        createFromQuestion={vi.fn()}
        createScan={createScan}
        getScan={vi.fn()}
        retryScan={vi.fn()}
        cancelScan={vi.fn()}
        exportScan={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Critères manuels"));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Univers de la recherche" }),
      "INDEX",
    );
    expect(await screen.findByRole("option", { name: "CAC 40 · général" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Demande à l’agent" })).toHaveValue(
      "Trouve dans l’indice CAC 40 les actions ayant baissé d’au moins 80 % sur 5 ans",
    );
    await user.click(screen.getByRole("button", { name: "Lancer ces critères" }));

    expect(createScan).toHaveBeenCalledWith(
      expect.objectContaining({ market: "INDEX", index_code: "CAC40" }),
    );
  });

  it("starts a complete national-market scan and updates the agent request", async () => {
    const user = userEvent.setup();
    const createScan = vi.fn().mockResolvedValue({
      ...queuedScan,
      criteria: {
        ...queuedScan.criteria,
        market: "COUNTRY",
        country_code: "FR",
      },
    });
    render(
      <MarketScanner
        listIndices={vi.fn().mockResolvedValue([])}
        listNationalMarkets={vi.fn().mockResolvedValue([
          {
            code: "FR",
            name: "France",
            region: "Europe",
            currency: "EUR",
            exchanges: ["PAR"],
          },
        ])}
        listScans={vi.fn().mockResolvedValue([])}
        createFromQuestion={vi.fn()}
        createScan={createScan}
        getScan={vi.fn()}
        retryScan={vi.fn()}
        cancelScan={vi.fn()}
        exportScan={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Critères manuels"));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Univers de la recherche" }),
      "COUNTRY",
    );
    expect(await screen.findByRole("option", { name: "France · EUR" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Demande à l’agent" })).toHaveValue(
      "Trouve sur le marché national de France les actions ayant baissé d’au moins 80 % sur 5 ans",
    );
    await user.click(screen.getByRole("button", { name: "Lancer ces critères" }));

    expect(createScan).toHaveBeenCalledWith(
      expect.objectContaining({
        market: "COUNTRY",
        index_code: null,
        country_code: "FR",
      }),
    );
  });
});

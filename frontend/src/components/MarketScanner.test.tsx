import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { MarketScan } from "../api/client";
import { MarketScanner } from "./MarketScanner";

const queuedScan: MarketScan = {
  id: "scan-1",
  status: "queued",
  criteria: {
    market: "US",
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

describe("MarketScanner", () => {
  it("starts a deterministic scan from a natural-language request", async () => {
    const user = userEvent.setup();
    const createFromQuestion = vi.fn().mockResolvedValue(queuedScan);
    const listScans = vi.fn().mockResolvedValue([]);
    render(
      <MarketScanner
        listScans={listScans}
        createFromQuestion={createFromQuestion}
        createScan={vi.fn()}
        getScan={vi.fn()}
        retryScan={vi.fn()}
        exportScan={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Scan du marché américain" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Lancer avec l’agent" }));

    expect(createFromQuestion).toHaveBeenCalledWith(
      "Trouve sur le marché américain les actions ayant baissé d’au moins 80 % sur 5 ans",
    );
    expect(await screen.findByText("En attente")).toBeInTheDocument();
  });
});

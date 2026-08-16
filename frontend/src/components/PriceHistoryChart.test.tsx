import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { PriceHistory } from "../api/client";
import { PriceHistoryChart } from "./PriceHistoryChart";

const history: PriceHistory = {
  company_id: "company-1",
  currency: "EUR",
  source: "Yahoo Finance",
  updated_at: "2026-08-16T10:00:00Z",
  points: [
    { date: "2021-08-16", close: 90, adjusted_close: 80 },
    { date: "2025-08-16", close: 105, adjusted_close: 100 },
    { date: "2026-08-16", close: 125, adjusted_close: 120 },
  ],
};

describe("PriceHistoryChart", () => {
  afterEach(cleanup);

  it("shows adjusted performance and allows changing the period", () => {
    render(<PriceHistoryChart history={history} />);

    expect(screen.getByRole("heading", { name: "Historique du cours de bourse" })).toBeInTheDocument();
    expect(screen.getByText("+50 % sur la période")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("80,00"));

    fireEvent.click(screen.getByRole("button", { name: "1 an" }));

    expect(screen.getByText("+20 % sur la période")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 an" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the analysis usable when no market history is available", () => {
    render(<PriceHistoryChart history={null} />);
    expect(screen.getByText("Historique indisponible pour cette valeur.")).toBeInTheDocument();
  });
});

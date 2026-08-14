import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Company, Screener } from "../api/client";
import { SectorScreener } from "./SectorScreener";

const companies: Company[] = [
  {
    id: "company-1",
    name: "Air Liquide",
    ticker: "AI.PA",
    exchange: "Euronext Paris",
    country: "France",
    currency: "EUR",
    sector: "Industrials",
    industry: "Specialty Chemicals",
    status: "ready",
  },
];

const screener: Screener = {
  summary: {
    companies: 2,
    classified: 2,
    eligible: 1,
    leaders: 1,
    sectors: 1,
    min_peer_count: 2,
  },
  sectors: ["Industrials"],
  companies: [
    {
      company_id: "company-1",
      name: "Air Liquide",
      ticker: "AI.PA",
      sector: "Industrials",
      sector_label: "Industrie",
      industry: "Specialty Chemicals",
      is_favorite: false,
      index_memberships: ["CAC40"],
      fiscal_year: 2025,
      absolute_score: 80,
      sector_score: 87.5,
      sector_rank: 1,
      peer_count: 4,
      data_coverage: 85,
      status: "leader",
      status_label: "Leader sectoriel",
      explanation: "Score relatif calculé sur 7 métriques.",
      metrics: [
        {
          key: "roic",
          label: "ROIC",
          value: 0.19,
          sector_median: 0.11,
          percentile: 92,
          weight: 15,
          higher_is_better: true,
        },
      ],
      updated_at: "2026-08-14T10:00:00Z",
    },
  ],
  disclaimer: "Classement de recherche, sans recommandation d’achat.",
};

describe("SectorScreener", () => {
  it("shows an explained sector-adjusted top candidate", async () => {
    const user = userEvent.setup();
    const onAnalysis = vi.fn();
    render(
      <SectorScreener
        screener={screener}
        companies={companies}
        onAnalysis={onAnalysis}
      />,
    );

    expect(screen.getByRole("heading", { name: "Sélection ajustée au secteur" })).toBeInTheDocument();
    expect(screen.getByText("87.5/100")).toBeInTheDocument();
    expect(screen.getByText("Rang 1/4")).toBeInTheDocument();
    expect(screen.getByText("0,19 · 92e percentile")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ouvrir l’analyse de Air Liquide" }));
    expect(onAnalysis).toHaveBeenCalledWith(companies[0]);
  });

  it("prepares existing classifications and reports the batch result", async () => {
    const user = userEvent.setup();
    const onPrepare = vi.fn().mockResolvedValue({
      requested: 2,
      processed: 2,
      classified: 2,
      imported: 0,
      unchanged: 0,
      failed: 0,
      remaining: 0,
      items: [],
    });
    render(
      <SectorScreener
        screener={screener}
        companies={companies}
        onAnalysis={vi.fn()}
        onPrepare={onPrepare}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Classer l’univers" }));

    expect(onPrepare).toHaveBeenCalledWith(false);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 classées · 0 historique chargé",
    );
  });
});

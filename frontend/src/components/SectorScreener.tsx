import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  DatabaseZap,
  Filter,
  Gauge,
  Layers3,
  Tags,
} from "lucide-react";

import type {
  Company,
  Screener,
  ScreenerPreparation,
} from "../api/client";

interface SectorScreenerProps {
  screener: Screener;
  companies: Company[];
  onAnalysis(company: Company): void;
  onPrepare?(importFinancials: boolean): Promise<ScreenerPreparation>;
}

const SECTOR_LABELS: Record<string, string> = {
  "Communication Services": "Services de communication",
  "Consumer Discretionary": "Consommation discrétionnaire",
  "Consumer Staples": "Consommation de base",
  Energy: "Énergie",
  Financials: "Finance",
  "Health Care": "Santé",
  Industrials: "Industrie",
  "Information Technology": "Technologie",
  Materials: "Matériaux",
  "Real Estate": "Immobilier",
  Utilities: "Services aux collectivités",
};

function formatMetric(value: number) {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  }).format(value);
}

export function SectorScreener({
  screener,
  companies,
  onAnalysis,
  onPrepare,
}: SectorScreenerProps) {
  const [sector, setSector] = useState("all");
  const [preparing, setPreparing] = useState<"classification" | "financials" | null>(null);
  const [preparationMessage, setPreparationMessage] = useState<string | null>(null);
  const [preparationError, setPreparationError] = useState<string | null>(null);
  const companyById = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies],
  );
  const candidates = useMemo(
    () =>
      screener.companies
        .filter(
          (company) =>
            company.sector_score !== null &&
            (sector === "all" || company.sector === sector),
        )
        .slice(0, 5),
    [screener.companies, sector],
  );
  const waitingCount = screener.summary.companies - screener.summary.eligible;
  const pendingFinancials = screener.companies.filter(
    (company) => company.fiscal_year === null,
  ).length;

  const prepare = async (importFinancials: boolean) => {
    if (!onPrepare) return;
    setPreparing(importFinancials ? "financials" : "classification");
    setPreparationMessage(null);
    setPreparationError(null);
    try {
      const result = await onPrepare(importFinancials);
      setPreparationMessage(
        `${result.classified} classée${result.classified > 1 ? "s" : ""} · ` +
          `${result.imported} historique${result.imported > 1 ? "s" : ""} chargé${result.imported > 1 ? "s" : ""}` +
          (result.failed ? ` · ${result.failed} échec${result.failed > 1 ? "s" : ""}` : ""),
      );
    } catch (error) {
      setPreparationError(
        error instanceof Error
          ? error.message
          : "La préparation de l’univers a échoué.",
      );
    } finally {
      setPreparing(null);
    }
  };

  return (
    <section
      className="section sector-screener"
      id="screener"
      aria-labelledby="screener-title"
    >
      <div className="sector-screener__head">
        <div>
          <p className="section-eyebrow">Moteur de sélection</p>
          <h2 id="screener-title">Sélection ajustée au secteur</h2>
          <p>
            Chaque entreprise est comparée aux sociétés de son propre secteur,
            métrique par métrique.
          </p>
        </div>
        <label className="sector-filter">
          <Filter aria-hidden="true" size={17} />
          <span className="sr-only">Filtrer le moteur par secteur</span>
          <select
            value={sector}
            onChange={(event) => setSector(event.target.value)}
            aria-label="Filtrer le moteur par secteur"
          >
            <option value="all">Tous les secteurs</option>
            {screener.sectors.map((item) => (
              <option key={item} value={item}>
                {SECTOR_LABELS[item] ?? item}
              </option>
            ))}
          </select>
        </label>
      </div>

      {onPrepare && screener.summary.companies > 0 && (
        <div className="screener-preparation">
          <div>
            <strong>Préparer l’univers</strong>
            <span>
              Complétez les secteurs existants, puis chargez les historiques
              encore absents par lots de dix.
            </span>
          </div>
          <div className="screener-preparation__actions">
            <button
              className="button button--secondary"
              disabled={preparing !== null}
              onClick={() => void prepare(false)}
            >
              <Tags aria-hidden="true" size={17} />
              {preparing === "classification" ? "Classement…" : "Classer l’univers"}
            </button>
            {pendingFinancials > 0 && (
              <button
                className="button button--primary"
                disabled={preparing !== null}
                onClick={() => void prepare(true)}
              >
                <DatabaseZap aria-hidden="true" size={17} />
                {preparing === "financials"
                  ? "Chargement…"
                  : `Charger ${Math.min(pendingFinancials, 10)} historique${pendingFinancials > 1 ? "s" : ""}`}
              </button>
            )}
          </div>
          {preparationMessage && (
            <p className="screener-preparation__message" role="status">
              {preparationMessage}
            </p>
          )}
          {preparationError && (
            <p className="form-error" role="alert">
              {preparationError}
            </p>
          )}
        </div>
      )}

      <dl className="screener-summary">
        <div>
          <dt>Entreprises comparables</dt>
          <dd>{screener.summary.eligible}</dd>
        </div>
        <div>
          <dt>Secteurs couverts</dt>
          <dd>{screener.summary.sectors}</dd>
        </div>
        <div>
          <dt>Leaders sectoriels</dt>
          <dd>{screener.summary.leaders}</dd>
        </div>
        <div>
          <dt>À compléter</dt>
          <dd>{waitingCount}</dd>
        </div>
      </dl>

      {candidates.length ? (
        <div className="screener-results" aria-label="Top 5 sectoriel">
          {candidates.map((candidate, position) => {
            const company = companyById.get(candidate.company_id);
            const strength = [...candidate.metrics].sort(
              (left, right) => right.percentile - left.percentile,
            )[0];
            return (
              <article className="screener-row" key={candidate.company_id}>
                <span className="screener-position" aria-label={`Position ${position + 1}`}>
                  {position + 1}
                </span>
                <div className="screener-company">
                  <strong>{candidate.name}</strong>
                  <span>
                    {candidate.ticker} · {candidate.sector_label}
                    {candidate.is_favorite ? " · Favori" : ""}
                  </span>
                </div>
                <div className="screener-score">
                  <Gauge aria-hidden="true" size={18} />
                  <span>Score sectoriel</span>
                  <strong>{candidate.sector_score}/100</strong>
                </div>
                <div className="screener-rank">
                  <Layers3 aria-hidden="true" size={18} />
                  <span>
                    Rang {candidate.sector_rank}/{candidate.peer_count}
                  </span>
                  <strong>{candidate.status_label}</strong>
                </div>
                <div className="screener-strength">
                  <span>Force principale</span>
                  <strong>{strength?.label ?? "Données disponibles"}</strong>
                  <small>
                    {strength
                      ? `${formatMetric(strength.value)} · ${strength.percentile}e percentile`
                      : candidate.explanation}
                  </small>
                </div>
                {company?.status === "ready" && (
                  <button
                    className="portfolio-open"
                    onClick={() => onAnalysis(company)}
                    aria-label={`Ouvrir l’analyse de ${candidate.name}`}
                  >
                    <ArrowUpRight aria-hidden="true" size={17} />
                  </button>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="screener-empty">
          <Layers3 aria-hidden="true" size={34} />
          <div>
            <h3>Le classement se prépare</h3>
            <p>
              Analysez au moins deux entreprises d’un même secteur et renseignez
              leur classification GICS pour obtenir un classement relatif.
            </p>
          </div>
        </div>
      )}

      <p className="screener-disclaimer">{screener.disclaimer}</p>
    </section>
  );
}

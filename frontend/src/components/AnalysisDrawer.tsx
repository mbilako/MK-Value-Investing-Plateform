import { Activity, X } from "lucide-react";

import type {
  Company,
  FinancialAnalysis,
  FinancialHistory,
  FinancialIndicator,
  ScoringAnalysis,
  ScoringPayload,
  ValuationAnalysis,
  ValuationPayload,
} from "../api/client";
import { ScorePanel } from "./ScorePanel";
import { ValuationPanel } from "./ValuationPanel";

interface AnalysisDrawerProps {
  company: Company;
  history: FinancialHistory | null;
  valuations: ValuationAnalysis[];
  scores: ScoringAnalysis[];
  loading: boolean;
  error: string | null;
  onCreateValuation: (payload: ValuationPayload) => Promise<ValuationAnalysis>;
  onCreateScore: (payload: ScoringPayload) => Promise<ScoringAnalysis>;
  onClose: () => void;
}

function formatAmount(value: number | null, currency: string): string {
  if (value == null) return "—";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M ${currency}`;
}

function formatRatio(numerator: number, denominator: number): string {
  if (denominator <= 0) return "—";
  return `${((numerator / denominator) * 100).toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
  })} %`;
}

function formatIndicator(indicator: FinancialIndicator): string {
  if (indicator.value == null) return "Non calculable";
  if (indicator.unit === "ratio") {
    return `${(indicator.value * 100).toLocaleString("fr-FR", {
      maximumFractionDigits: 1,
    })} %`;
  }
  if (indicator.unit === "multiple") {
    return `${indicator.value.toLocaleString("fr-FR", {
      maximumFractionDigits: 2,
    })}×`;
  }
  return formatAmount(indicator.value, indicator.unit);
}

function formatGrowth(value: number | null): string {
  if (value == null) return "Historique insuffisant";
  return `${(value * 100).toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
  })} % / an`;
}

function operatingCashFlow(snapshot: FinancialAnalysis): string {
  return formatAmount(snapshot.operating_cash_flow, snapshot.currency);
}

export function AnalysisDrawer({
  company,
  history,
  valuations,
  scores,
  loading,
  error,
  onCreateValuation,
  onCreateScore,
  onClose,
}: AnalysisDrawerProps) {
  const latest = history?.snapshots[0];
  const trend = history?.trend;

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        onClick={onClose}
        aria-label="Fermer l’analyse financière"
      />
      <aside
        className="drawer drawer--wide analysis-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-title"
      >
        <div className="drawer__head">
          <div>
            <h2 id="analysis-title">Historique fondamental</h2>
            <p>
              {company.name} · {company.ticker}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" />
          </button>
        </div>

        <div className="analysis-drawer__body">
          {loading && <p className="analysis-message">Chargement de l’analyse…</p>}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {!loading && !error && !latest && (
            <p className="analysis-message">Aucune analyse disponible.</p>
          )}
          {latest && history && (
            <>
              <div className="analysis-context">
                <span>
                  {history.snapshots.length} exercice
                  {history.snapshots.length > 1 ? "s" : ""} disponible
                  {history.snapshots.length > 1 ? "s" : ""}
                </span>
                <span>
                  {trend?.first_year}–{trend?.last_year}
                </span>
              </div>

              {latest.analysis_profile === "financial" ? (
                <section className="financial-profile-note">
                  <Activity aria-hidden="true" size={24} />
                  <div>
                    <h3>Profil banque ou assurance</h3>
                    <p>
                      Les fondamentaux sont présentés sur la durée. Le MK Score
                      industriel reste non applicable, car ses ratios de dette,
                      de liquidité et d’EBITDA seraient trompeurs ici.
                    </p>
                  </div>
                </section>
              ) : (
                <section className="mk-score-summary" aria-label="Dernier MK Score">
                  <div>
                    <span>MK Score</span>
                    <strong>{latest.mk_score ?? "—"}/100</strong>
                  </div>
                  <p>
                    Dernier exercice disponible : {latest.fiscal_year}. La table
                    ci-dessous permet de vérifier sa stabilité dans le temps.
                  </p>
                </section>
              )}

              <section className="analysis-section" aria-labelledby="fundamentals-title">
                <div className="analysis-section__head">
                  <h3 id="fundamentals-title">Fondamentaux du dernier exercice</h3>
                  <span>{latest.fiscal_year} · montants en millions</span>
                </div>
                <div className="indicator-grid indicator-grid--fundamentals">
                  <article className="indicator-card">
                    <span>Revenus publiés</span>
                    <strong>{formatAmount(latest.revenue, latest.currency)}</strong>
                  </article>
                  <article className="indicator-card">
                    <span>Résultat net</span>
                    <strong>{formatAmount(latest.net_income, latest.currency)}</strong>
                  </article>
                  <article className="indicator-card">
                    <span>Rendement des capitaux propres</span>
                    <strong>{formatRatio(latest.net_income, latest.total_equity)}</strong>
                  </article>
                  <article className="indicator-card">
                    <span>Capitaux propres / total actif</span>
                    <strong>{formatRatio(latest.total_equity, latest.total_assets)}</strong>
                  </article>
                  <article className="indicator-card">
                    <span>Flux de trésorerie d’exploitation</span>
                    <strong>{operatingCashFlow(latest)}</strong>
                  </article>
                  <article className="indicator-card">
                    <span>Capitalisation boursière</span>
                    <strong>{formatAmount(latest.market_cap, latest.currency)}</strong>
                  </article>
                </div>
              </section>

              <section className="analysis-section" aria-labelledby="history-title">
                <div className="analysis-section__head">
                  <h3 id="history-title">Historique annuel</h3>
                  <span>Jusqu’aux 10 derniers exercices disponibles</span>
                </div>
                <div className="fundamental-history" role="table" aria-label="Historique fondamental">
                  <div className="fundamental-history__head" role="row">
                    <span>Exercice</span>
                    <span>Revenus</span>
                    <span>Résultat net</span>
                    <span>ROE</span>
                    <span>Fonds propres / actif</span>
                    <span>Cash-flow d’exploitation</span>
                    <span>MK Score</span>
                  </div>
                  {history.snapshots.slice(0, 10).map((snapshot) => (
                    <div className="fundamental-history__row" role="row" key={snapshot.id}>
                      <strong>{snapshot.fiscal_year}</strong>
                      <span>{formatAmount(snapshot.revenue, snapshot.currency)}</span>
                      <span>{formatAmount(snapshot.net_income, snapshot.currency)}</span>
                      <span>{formatRatio(snapshot.net_income, snapshot.total_equity)}</span>
                      <span>{formatRatio(snapshot.total_equity, snapshot.total_assets)}</span>
                      <span>{operatingCashFlow(snapshot)}</span>
                      <strong>{snapshot.mk_score == null ? "N/A" : `${snapshot.mk_score}/100`}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="analysis-section" aria-labelledby="growth-title">
                <div className="analysis-section__head">
                  <h3 id="growth-title">Tendance annualisée</h3>
                  {trend && trend.periods >= 2 && (
                    <span>
                      {trend.first_year}–{trend.last_year}
                    </span>
                  )}
                </div>
                {!trend || trend.periods < 2 ? (
                  <p className="analysis-message">Historique insuffisant</p>
                ) : (
                  <div className="growth-grid">
                    <article>
                      <span>Revenus</span>
                      <strong>{formatGrowth(trend.revenue_cagr)}</strong>
                    </article>
                    <article>
                      <span>Résultat net</span>
                      <strong>{formatGrowth(trend.net_income_cagr)}</strong>
                    </article>
                    <article>
                      <span>Free Cash Flow</span>
                      <strong>{formatGrowth(trend.free_cash_flow_cagr)}</strong>
                    </article>
                  </div>
                )}
              </section>

              <details className="analysis-details">
                <summary>Voir les ratios détaillés du dernier exercice</summary>
                <div className="indicator-grid">
                  {latest.indicators.map((indicator) => (
                    <article className="indicator-card" key={indicator.key}>
                      <span>{indicator.label}</span>
                      <strong>{formatIndicator(indicator)}</strong>
                      <small>{indicator.formula}</small>
                    </article>
                  ))}
                </div>
              </details>

              {latest.analysis_profile !== "financial" && (
                <details className="analysis-details">
                  <summary>Valorisation et score global</summary>
                  <ValuationPanel
                    snapshot={latest}
                    valuations={valuations}
                    onCreate={onCreateValuation}
                  />
                  <ScorePanel
                    fiscalYear={latest.fiscal_year}
                    valuations={valuations}
                    scores={scores}
                    onCreate={onCreateScore}
                  />
                </details>
              )}

              <p className="analysis-disclaimer">
                Indicateurs de présélection explicables, sans recommandation
                d’investissement. Vérifier les chiffres dans les publications
                réglementaires.
              </p>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

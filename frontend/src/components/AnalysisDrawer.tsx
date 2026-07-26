import { Activity, ShieldCheck, Sparkles, X } from "lucide-react";

import type {
  Company,
  FinancialHistory,
  FinancialIndicator,
  ValuationAnalysis,
  ValuationPayload,
} from "../api/client";
import { ValuationPanel } from "./ValuationPanel";

interface AnalysisDrawerProps {
  company: Company;
  history: FinancialHistory | null;
  valuations: ValuationAnalysis[];
  loading: boolean;
  error: string | null;
  onCreateValuation: (
    payload: ValuationPayload,
  ) => Promise<ValuationAnalysis>;
  onClose: () => void;
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
  return `${indicator.value.toLocaleString("fr-FR", {
    maximumFractionDigits: 2,
  })} M ${indicator.unit}`;
}

function formatGrowth(value: number | null): string {
  if (value == null) return "Historique insuffisant";
  return `${(value * 100).toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
  })} % / an`;
}

export function AnalysisDrawer({
  company,
  history,
  valuations,
  loading,
  error,
  onCreateValuation,
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
            <h2 id="analysis-title">Analyse financière</h2>
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
          {latest && (
            <>
              <div className="analysis-context">
                <span>Exercice {latest.fiscal_year}</span>
                <span>{latest.source}</span>
              </div>
              <section className="score-grid" aria-label="Scores spécialisés">
                <article className="score-card score-card--global">
                  <Activity aria-hidden="true" size={22} />
                  <span>MK Score</span>
                  <strong>{latest.mk_score}</strong>
                </article>
                <article className="score-card">
                  <Sparkles aria-hidden="true" size={22} />
                  <span>Quality Score</span>
                  <strong>{latest.quality_score}</strong>
                </article>
                <article className="score-card">
                  <ShieldCheck aria-hidden="true" size={22} />
                  <span>Safety Score</span>
                  <strong>{latest.safety_score}</strong>
                </article>
              </section>

              <section
                className="analysis-section"
                aria-labelledby="indicators-title"
              >
                <div className="analysis-section__head">
                  <h3 id="indicators-title">Indicateurs fondamentaux</h3>
                  <span>Montants en millions</span>
                </div>
                <div className="indicator-grid">
                  {latest.indicators.map((indicator) => (
                    <article className="indicator-card" key={indicator.key}>
                      <span>{indicator.label}</span>
                      <strong>{formatIndicator(indicator)}</strong>
                      <small>{indicator.formula}</small>
                    </article>
                  ))}
                </div>
              </section>

              <section
                className="analysis-section"
                aria-labelledby="growth-title"
              >
                <div className="analysis-section__head">
                  <h3 id="growth-title">Croissance annualisée</h3>
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
                      <span>Chiffre d’affaires</span>
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

              <ValuationPanel
                snapshot={latest}
                valuations={valuations}
                onCreate={onCreateValuation}
              />

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

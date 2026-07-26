import { useState } from "react";
import {
  CircleAlert,
  CircleCheck,
  Gauge,
  Info,
  RefreshCw,
} from "lucide-react";

import type {
  ScoringAnalysis,
  ScoringInsight,
  ScoringPayload,
  ValuationAnalysis,
} from "../api/client";

interface ScorePanelProps {
  fiscalYear: number;
  valuations: ValuationAnalysis[];
  scores: ScoringAnalysis[];
  onCreate: (payload: ScoringPayload) => Promise<ScoringAnalysis>;
}

function formatScore(value: number): string {
  return value.toLocaleString("fr-FR", {
    maximumFractionDigits: 2,
  });
}

function insightIcon(tone: ScoringInsight["tone"]) {
  if (tone === "positive") return CircleCheck;
  if (tone === "caution") return CircleAlert;
  return Info;
}

export function ScorePanel({
  fiscalYear,
  valuations,
  scores,
  onCreate,
}: ScorePanelProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valuation = valuations.find((item) => item.fiscal_year === fiscalYear);
  const latest = scores.find((item) => item.fiscal_year === fiscalYear);

  const calculate = async () => {
    if (!valuation) return;
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        fiscal_year: fiscalYear,
        valuation_id: valuation.id,
      });
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Le scoring global n’a pas pu être calculé.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="analysis-section scoring-section">
      <div className="analysis-section__head">
        <h3>Scoring global</h3>
        <span>Exercice {fiscalYear}</span>
      </div>

      {latest && (
        <>
          <div className="scoring-summary">
            <article
              aria-label="MK Global Score"
              className={`scoring-summary__score scoring-signal--${latest.signal}`}
            >
              <Gauge aria-hidden="true" size={23} />
              <span>MK Global Score</span>
              <strong>{formatScore(latest.global_score)}</strong>
              <small>/ 100</small>
            </article>
            <article className="scoring-summary__signal">
              <span>Signal de présélection</span>
              <strong>{latest.signal_label}</strong>
              <p>
                Synthèse de recherche explicable, sans recommandation
                d’investissement.
              </p>
            </article>
          </div>

          <div className="scoring-components">
            {latest.components.map((component) => (
              <article key={component.key}>
                <div className="scoring-components__head">
                  <strong>{component.label}</strong>
                  <b>{formatScore(component.score)}</b>
                </div>
                <div
                  className="score-progress"
                  aria-label={`${component.label} : ${formatScore(
                    component.score,
                  )} sur 100`}
                >
                  <span style={{ width: `${component.score}%` }} />
                </div>
                <small>
                  Poids {(component.weight * 100).toLocaleString("fr-FR")} %
                  · contribution {formatScore(component.contribution)}
                </small>
                <p>{component.note}</p>
              </article>
            ))}
          </div>

          <ul className="scoring-insights" aria-label="Explication du scoring">
            {latest.insights.map((insight) => {
              const InsightIcon = insightIcon(insight.tone);
              return (
                <li data-tone={insight.tone} key={insight.key}>
                  <InsightIcon aria-hidden="true" size={17} />
                  <span>{insight.label}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {!valuation && !latest && (
        <p className="analysis-message">
          Créez d’abord une valorisation calculable pour activer le scoring.
        </p>
      )}

      {valuation && (
        <button
          className="button button--secondary scoring-action"
          type="button"
          disabled={submitting}
          onClick={calculate}
        >
          <RefreshCw aria-hidden="true" size={17} />
          {submitting
            ? "Calcul du scoring…"
            : latest
              ? "Recalculer le scoring global"
              : "Calculer le scoring global"}
        </button>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

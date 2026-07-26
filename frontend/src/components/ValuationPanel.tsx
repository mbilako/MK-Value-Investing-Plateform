import { FormEvent, useState } from "react";
import { Calculator, RefreshCw } from "lucide-react";

import type {
  FinancialAnalysis,
  ValuationAnalysis,
  ValuationPayload,
} from "../api/client";

interface ValuationPanelProps {
  snapshot: FinancialAnalysis;
  valuations: ValuationAnalysis[];
  onCreate: (payload: ValuationPayload) => Promise<ValuationAnalysis>;
}

const initialAssumptions = {
  growth_rate: "5",
  terminal_growth_rate: "2",
  cost_of_equity: "10",
  wacc: "8",
  tax_rate: "25",
  projection_years: "5",
  target_pe: "15",
  corporate_bond_yield: "4.4",
  margin_of_safety: "25",
};

type AssumptionKey = keyof typeof initialAssumptions;

const assumptionFields: Array<{
  key: AssumptionKey;
  label: string;
  suffix: string;
  min: string;
  max: string;
}> = [
  {
    key: "growth_rate",
    label: "Croissance annuelle",
    suffix: "%",
    min: "-99",
    max: "50",
  },
  {
    key: "terminal_growth_rate",
    label: "Croissance terminale",
    suffix: "%",
    min: "-5",
    max: "10",
  },
  {
    key: "cost_of_equity",
    label: "Coût des capitaux propres",
    suffix: "%",
    min: "0.1",
    max: "50",
  },
  {
    key: "wacc",
    label: "WACC",
    suffix: "%",
    min: "0.1",
    max: "50",
  },
  {
    key: "tax_rate",
    label: "Taux d’impôt",
    suffix: "%",
    min: "0",
    max: "100",
  },
  {
    key: "projection_years",
    label: "Horizon de projection",
    suffix: "ans",
    min: "1",
    max: "10",
  },
  {
    key: "target_pe",
    label: "PER cible",
    suffix: "×",
    min: "0.1",
    max: "100",
  },
  {
    key: "corporate_bond_yield",
    label: "Rendement obligataire AAA",
    suffix: "%",
    min: "0.1",
    max: "50",
  },
  {
    key: "margin_of_safety",
    label: "Marge de sécurité",
    suffix: "%",
    min: "0",
    max: "90",
  },
];

function formatMoney(value: number | null, currency: string): string {
  if (value == null) return "Non calculable";
  return `${value.toLocaleString("fr-FR", {
    maximumFractionDigits: 2,
  })} M ${currency}`;
}

function formatGap(value: number | null): string {
  if (value == null) return "Non calculable";
  return `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
  })} %`;
}

function categoryLabel(category: ValuationAnalysis["methods"][number]["category"]) {
  if (category === "intrinsic") return "Valeur intrinsèque";
  if (category === "relative") return "Prix relatif";
  return "Proxy";
}

export function ValuationPanel({
  snapshot,
  valuations,
  onCreate,
}: ValuationPanelProps) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState(initialAssumptions);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = valuations[0];

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        fiscal_year: snapshot.fiscal_year,
        assumptions: {
          growth_rate: Number(values.growth_rate) / 100,
          terminal_growth_rate:
            Number(values.terminal_growth_rate) / 100,
          cost_of_equity: Number(values.cost_of_equity) / 100,
          wacc: Number(values.wacc) / 100,
          tax_rate: Number(values.tax_rate) / 100,
          projection_years: Number(values.projection_years),
          target_pe: Number(values.target_pe),
          corporate_bond_yield:
            Number(values.corporate_bond_yield) / 100,
          margin_of_safety: Number(values.margin_of_safety) / 100,
        },
      });
      setEditing(false);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La valorisation n’a pas pu être calculée.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="analysis-section valuation-section">
      <div className="analysis-section__head">
        <h3>Valorisation</h3>
        <span>Exercice {snapshot.fiscal_year}</span>
      </div>

      {latest && (
        <>
          <div className="valuation-summary">
            <article
              aria-label="Estimation centrale"
              className="valuation-summary__primary"
            >
              <Calculator aria-hidden="true" size={22} />
              <span>Estimation centrale</span>
              <strong>
                {formatMoney(latest.central_estimate, latest.currency)}
              </strong>
            </article>
            <article>
              <span>Valeur avec marge de sécurité</span>
              <strong>
                {formatMoney(
                  latest.margin_of_safety_value,
                  latest.currency,
                )}
              </strong>
            </article>
            <article>
              <span>Écart avec la capitalisation</span>
              <strong>{formatGap(latest.market_gap)}</strong>
            </article>
          </div>

          <div className="valuation-methods">
            {latest.methods.map((method) => (
              <article key={method.key}>
                <div>
                  <span>{categoryLabel(method.category)}</span>
                  <strong>{method.label}</strong>
                </div>
                <b>{formatMoney(method.value, latest.currency)}</b>
                <small>{method.formula}</small>
                <p>{method.note}</p>
              </article>
            ))}
          </div>
        </>
      )}

      {!editing && (
        <button
          className="button button--secondary valuation-action"
          type="button"
          onClick={() => setEditing(true)}
        >
          <RefreshCw aria-hidden="true" size={17} />
          {latest
            ? "Recalculer la valorisation"
            : "Préparer une valorisation"}
        </button>
      )}

      {editing && (
        <form className="valuation-form" onSubmit={submit}>
          <div className="valuation-form__head">
            <div>
              <h4>Hypothèses de valorisation</h4>
              <p>
                Valeurs initiales indicatives à vérifier avant le calcul.
              </p>
            </div>
            <button
              className="button button--text"
              type="button"
              onClick={() => setEditing(false)}
            >
              Annuler
            </button>
          </div>
          <div className="valuation-fields">
            {assumptionFields.map((field) => (
              <div className="field" key={field.key}>
                <label htmlFor={`valuation-${field.key}`}>
                  {field.label}
                </label>
                <div className="input-with-suffix">
                  <input
                    id={`valuation-${field.key}`}
                    type="number"
                    step="any"
                    min={field.min}
                    max={field.max}
                    required
                    value={values[field.key]}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                  />
                  <span>{field.suffix}</span>
                </div>
              </div>
            ))}
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button button--primary"
            type="submit"
            disabled={submitting}
          >
            <Calculator aria-hidden="true" size={18} />
            {submitting ? "Calcul en cours…" : "Estimer la valeur"}
          </button>
        </form>
      )}
    </section>
  );
}

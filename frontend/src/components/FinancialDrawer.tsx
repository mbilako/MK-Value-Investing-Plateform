import { FormEvent, useState } from "react";
import { X } from "lucide-react";

import type {
  Company,
  FinancialPayload,
} from "../api/client";

interface FinancialDrawerProps {
  company: Company;
  onClose: () => void;
  onSubmit: (payload: FinancialPayload) => Promise<void>;
}

type NumericFinancialField = Exclude<
  keyof FinancialPayload,
  "fiscal_year" | "source" | "currency"
>;

const numericFields: Array<{
  key: NumericFinancialField;
  label: string;
}> = [
  { key: "revenue", label: "Chiffre d’affaires" },
  { key: "ebitda", label: "EBITDA" },
  {
    key: "depreciation_amortization",
    label: "Dotations aux amortissements",
  },
  { key: "ebit", label: "EBIT" },
  { key: "interest_expense", label: "Charges d’intérêts" },
  { key: "capex", label: "Investissements (Capex)" },
  { key: "net_income", label: "Résultat net" },
  { key: "market_cap", label: "Capitalisation boursière" },
  { key: "total_assets", label: "Total actif" },
  { key: "current_assets", label: "Actif circulant" },
  { key: "current_liabilities", label: "Passif exigible" },
  { key: "financial_debt", label: "Dette financière" },
  { key: "cash", label: "Trésorerie" },
  { key: "total_equity", label: "Capitaux propres" },
];

export function FinancialDrawer({
  company,
  onClose,
  onSubmit,
}: FinancialDrawerProps) {
  const [source, setSource] = useState("");
  const [fiscalYear, setFiscalYear] = useState("2025");
  const [values, setValues] = useState<Record<NumericFinancialField, string>>(
    Object.fromEntries(
      numericFields.map(({ key }) => [key, ""]),
    ) as Record<NumericFinancialField, string>,
  );
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        fiscal_year: Number(fiscalYear),
        source,
        currency: company.currency,
        ...Object.fromEntries(
          numericFields.map(({ key }) => [key, Number(values[key])]),
        ),
      } as FinancialPayload);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        onClick={onClose}
        aria-label="Fermer le formulaire financier"
      />
      <aside
        className="drawer drawer--wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="financial-import-title"
      >
        <div className="drawer__head">
          <div>
            <h2 id="financial-import-title">
              Importer les données financières
            </h2>
            <p>
              {company.name} · {company.ticker}
            </p>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Fermer"
          >
            <X aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={submit}>
          <div className="drawer__fields">
            <div className="financial-context">
              <div className="field">
                <label htmlFor="financial-year">Exercice</label>
                <input
                  id="financial-year"
                  type="number"
                  min="1900"
                  max="2100"
                  required
                  value={fiscalYear}
                  onChange={(event) => setFiscalYear(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="financial-source">Source</label>
                <input
                  id="financial-source"
                  required
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  placeholder="Rapport annuel, dépôt réglementaire…"
                />
              </div>
            </div>
            <p className="financial-unit">
              Montants exprimés en millions de {company.currency}.
            </p>
            <div className="financial-grid">
              {numericFields.map(({ key, label }) => (
                <div className="field" key={key}>
                  <label htmlFor={`financial-${key}`}>{label}</label>
                  <input
                    id={`financial-${key}`}
                    type="number"
                    step="any"
                    min="0"
                    required
                    value={values[key]}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [key]: event.target.value,
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="drawer__actions">
            <button
              className="button button--secondary"
              type="button"
              onClick={onClose}
            >
              Annuler
            </button>
            <button className="button button--primary" disabled={submitting}>
              {submitting ? "Calcul en cours…" : "Calculer le MK Score"}
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}

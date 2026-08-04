import { useState } from "react";
import { CloudDownload, X } from "lucide-react";

import type { Company } from "../api/client";

interface FinancialDrawerProps {
  company: Company;
  onClose: () => void;
  onAutomaticSubmit: () => Promise<void>;
}

export function FinancialDrawer({
  company,
  onClose,
  onAutomaticSubmit,
}: FinancialDrawerProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitAutomatically = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await onAutomaticSubmit();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Le chargement de l’historique a échoué.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        onClick={onClose}
        aria-label="Fermer le chargement de l’historique"
      />
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="financial-import-title"
      >
        <div className="drawer__head">
          <div>
            <h2 id="financial-import-title">Charger l’historique financier</h2>
            <p>
              {company.name} · {company.ticker}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" />
          </button>
        </div>
        <div className="drawer__fields">
          <section
            className="automatic-import automatic-import--simple"
            aria-labelledby="automatic-import-title"
          >
            <CloudDownload aria-hidden="true" size={28} />
            <div>
              <h3 id="automatic-import-title">Jusqu’à 10 exercices</h3>
              <p>
                MK-VIP rassemble les exercices annuels disponibles auprès des
                sources gratuites, calcule un MK Score par année lorsque le
                modèle est applicable, puis affiche la tendance de long terme.
              </p>
              <small>
                Yahoo Finance, SEC EDGAR et dépôts réglementaires ESEF. Certaines
                sociétés peuvent disposer de moins de dix exercices structurés.
              </small>
            </div>
          </section>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
        <div className="drawer__actions">
          <button className="button button--secondary" onClick={onClose}>
            Annuler
          </button>
          <button
            className="button button--primary"
            disabled={submitting}
            onClick={submitAutomatically}
          >
            {submitting ? "Chargement en cours…" : "Charger l’historique"}
          </button>
        </div>
      </aside>
    </div>
  );
}

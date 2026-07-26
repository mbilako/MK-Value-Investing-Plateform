import { FormEvent, useState } from "react";
import { X } from "lucide-react";

import type { CompanyPayload } from "../api/client";

interface ImportDrawerProps {
  onClose: () => void;
  onSubmit: (payload: CompanyPayload) => Promise<void>;
}

const airLiquide: CompanyPayload = {
  name: "Air Liquide",
  ticker: "AI.PA",
  exchange: "Euronext Paris",
  country: "France",
  currency: "EUR",
};

export function ImportDrawer({ onClose, onSubmit }: ImportDrawerProps) {
  const [form, setForm] = useState(airLiquide);
  const [submitting, setSubmitting] = useState(false);

  const update = (field: keyof CompanyPayload, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        ...form,
        ticker: form.ticker.toUpperCase(),
        currency: form.currency.toUpperCase(),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        onClick={onClose}
        aria-label="Fermer le formulaire"
      />
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-title"
      >
        <div className="drawer__head">
          <div>
            <h2 id="import-title">Importer une entreprise</h2>
            <p>Ajoutez une société à votre univers d’investissement.</p>
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
            <div className="field">
              <label htmlFor="company-name">Nom de l’entreprise</label>
              <input
                id="company-name"
                required
                value={form.name}
                onChange={(event) => update("name", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="company-ticker">Ticker</label>
              <input
                id="company-ticker"
                aria-describedby="ticker-help"
                required
                value={form.ticker}
                onChange={(event) => update("ticker", event.target.value)}
              />
              <small id="ticker-help">
                Le ticker sera normalisé en majuscules.
              </small>
            </div>
            <div className="field">
              <label htmlFor="company-exchange">Place de cotation</label>
              <input
                id="company-exchange"
                required
                value={form.exchange}
                onChange={(event) => update("exchange", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="company-country">Pays</label>
              <input
                id="company-country"
                required
                value={form.country}
                onChange={(event) => update("country", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="company-currency">Devise</label>
              <input
                id="company-currency"
                required
                maxLength={3}
                value={form.currency}
                onChange={(event) => update("currency", event.target.value)}
              />
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
              {submitting ? "Import en cours…" : "Importer"}
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}

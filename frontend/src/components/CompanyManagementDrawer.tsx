import { useState } from "react";
import { Archive, Save, Trash2, X } from "lucide-react";

import type { Company, CompanyPayload } from "../api/client";

interface CompanyManagementDrawerProps {
  company: Company;
  onUpdate(payload: Partial<CompanyPayload>): Promise<void>;
  onArchive(): Promise<void>;
  onDelete(): Promise<void>;
  onClose(): void;
}

export function CompanyManagementDrawer({
  company,
  onUpdate,
  onArchive,
  onDelete,
  onClose,
}: CompanyManagementDrawerProps) {
  const [form, setForm] = useState({
    name: company.name,
    ticker: company.ticker,
    exchange: company.exchange,
    country: company.country,
    currency: company.currency,
    isin: company.isin ?? "",
    cik: company.cik ?? "",
    lei: company.lei ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onClose();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "L’opération n’a pas pu être terminée.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button className="drawer-backdrop" onClick={onClose} aria-label="Fermer" />
      <aside
        className="drawer management-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="manage-title"
      >
        <header className="drawer__head">
          <div>
            <p className="section-eyebrow">Gestion de l’entreprise</p>
            <h2 id="manage-title">Modifier {company.name}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" size={20} />
          </button>
        </header>
        <form
          className="drawer__form"
          onSubmit={(event) => {
            event.preventDefault();
            void run(() =>
              onUpdate({
                ...form,
                isin: form.isin || null,
                cik: form.cik || null,
                lei: form.lei || null,
              }),
            );
          }}
        >
          <div className="drawer__fields management-fields">
            <label className="field field--wide">
              <span>Nom de l’entreprise</span>
              <input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Ticker</span>
              <input
                required
                value={form.ticker}
                onChange={(event) => setForm({ ...form, ticker: event.target.value })}
              />
            </label>
            <label className="field">
              <span>Devise</span>
              <input
                required
                maxLength={3}
                value={form.currency}
                onChange={(event) => setForm({ ...form, currency: event.target.value })}
              />
            </label>
            <label className="field field--wide">
              <span>Place de cotation</span>
              <input
                required
                value={form.exchange}
                onChange={(event) => setForm({ ...form, exchange: event.target.value })}
              />
            </label>
            <label className="field field--wide">
              <span>Pays</span>
              <input
                required
                value={form.country}
                onChange={(event) => setForm({ ...form, country: event.target.value })}
              />
            </label>
            <label className="field field--wide">
              <span>ISIN</span>
              <input
                maxLength={12}
                placeholder="Facultatif"
                value={form.isin}
                onChange={(event) => setForm({ ...form, isin: event.target.value })}
              />
            </label>
            <label className="field">
              <span>CIK (SEC)</span>
              <input
                maxLength={10}
                placeholder="Facultatif"
                value={form.cik}
                onChange={(event) => setForm({ ...form, cik: event.target.value })}
              />
            </label>
            <label className="field">
              <span>LEI</span>
              <input
                maxLength={20}
                placeholder="Facultatif"
                value={form.lei}
                onChange={(event) => setForm({ ...form, lei: event.target.value })}
              />
            </label>
            {error && <p className="form-error field--wide">{error}</p>}
            <section className="management-danger field--wide">
              <h3>Retirer de l’univers</h3>
              <p>
                L’archivage est réversible et conserve les analyses. La suppression
                définitive efface aussi l’historique associé.
              </p>
              <div>
                <button
                  type="button"
                  className="button button--secondary"
                  disabled={busy}
                  onClick={() => void run(onArchive)}
                >
                  <Archive aria-hidden="true" size={17} />
                  Archiver
                </button>
                <button
                  type="button"
                  className="button button--danger"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        `Supprimer définitivement ${company.name} et toutes ses analyses ?`,
                      )
                    ) {
                      void run(onDelete);
                    }
                  }}
                >
                  <Trash2 aria-hidden="true" size={17} />
                  Supprimer définitivement
                </button>
              </div>
            </section>
          </div>
          <footer className="drawer__actions">
            <button type="button" className="button button--ghost" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="button button--primary" disabled={busy}>
              <Save aria-hidden="true" size={17} />
              Enregistrer
            </button>
          </footer>
        </form>
      </aside>
    </div>
  );
}

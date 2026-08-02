import { useMemo, useState } from "react";
import { FileUp, Inbox, Plus, Search, Settings2 } from "lucide-react";

import type { Company } from "../api/client";

interface CompanyUniverseProps {
  companies: Company[];
  scores: Record<string, number>;
  onImport: () => void;
  onFinancialImport: (company: Company) => void;
  onAnalysis: (company: Company) => void;
  onManage: (company: Company) => void;
}

export function CompanyUniverse({
  companies,
  scores,
  onImport,
  onFinancialImport,
  onAnalysis,
  onManage,
}: CompanyUniverseProps) {
  const [query, setQuery] = useState("");
  const scoreFor = (company: Company) =>
    scores[company.id] ?? company.latest_mk_score;
  const filteredCompanies = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");
    if (!normalizedQuery) return companies;
    return companies.filter((company) =>
      `${company.name} ${company.ticker}`
        .toLocaleLowerCase("fr")
        .includes(normalizedQuery),
    );
  }, [companies, query]);

  return (
    <section className="section" aria-labelledby="universe-title">
      <h2 id="universe-title">Univers d’investissement</h2>
      <label className="search-field">
        <Search aria-hidden="true" size={21} strokeWidth={1.75} />
        <span className="sr-only">Rechercher une entreprise ou un ticker</span>
        <input
          placeholder="Rechercher une entreprise ou un ticker"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className="company-table">
        <div className="company-table__head" role="row">
          <span>Entreprise</span>
          <span>Ticker</span>
          <span>Place de cotation</span>
          <span>Pays</span>
          <span>Statut</span>
        </div>
        {companies.length ? (
          <div className="company-table__body">
            {filteredCompanies.map((company) => (
              <div className="company-table__row" role="row" key={company.id}>
                <div className="company-name-cell">
                  <strong>{company.name}</strong>
                  {company.index_memberships?.length ? (
                    <span className="index-badges">
                      {company.index_memberships.map((index) => (
                        <small key={index}>{index.replace("CACNEXT20", "CAC Next 20")}</small>
                      ))}
                    </span>
                  ) : null}
                </div>
                <span className="ticker">{company.ticker}</span>
                <span>{company.exchange}</span>
                <span>{company.country}</span>
                <div className="company-row-actions">
                  {company.status === "pending" ? (
                    <button
                      className="company-action"
                      onClick={() => onFinancialImport(company)}
                      aria-label={`Importer les données financières pour ${company.name}`}
                    >
                      <FileUp aria-hidden="true" size={16} />
                      Ajouter les données
                    </button>
                  ) : (
                    <button
                      className="company-status company-status--ready company-analysis"
                      onClick={() => onAnalysis(company)}
                      aria-label={`Voir l’analyse financière de ${company.name}`}
                    >
                      <span className="status-dot" aria-hidden="true" />
                      <span>Analyse prête</span>
                      {scoreFor(company) != null && (
                        <strong>MK Score {scoreFor(company)}</strong>
                      )}
                    </button>
                  )}
                  <button
                    className="row-manage"
                    onClick={() => onManage(company)}
                    aria-label={`Modifier ou retirer ${company.name}`}
                    title="Modifier ou retirer"
                  >
                    <Settings2 aria-hidden="true" size={17} />
                  </button>
                </div>
              </div>
            ))}
            {!filteredCompanies.length && (
              <p className="company-filter-empty">
                Aucune entreprise ne correspond à cette recherche.
              </p>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <Inbox aria-hidden="true" size={40} strokeWidth={1.5} />
            <h3>Aucune entreprise importée</h3>
            <p>
              Ajoutez une première société pour préparer son analyse fondamentale.
            </p>
            <button className="button button--secondary" onClick={onImport}>
              <Plus aria-hidden="true" size={18} />
              Commencer avec Air Liquide
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

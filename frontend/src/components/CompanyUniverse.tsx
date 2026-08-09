import { useMemo, useState } from "react";
import { FileUp, Inbox, Landmark, Search, Settings2, Star } from "lucide-react";

import type { Company } from "../api/client";

interface CompanyUniverseProps {
  companies: Company[];
  scores: Record<string, number>;
  onExploreIndices: () => void;
  onFinancialImport: (company: Company) => void;
  onAnalysis: (company: Company) => void;
  onManage: (company: Company) => void;
  onToggleFavorite: (company: Company, isFavorite: boolean) => void;
}

const INDEX_LABELS: Record<string, string> = {
  CAC40: "CAC 40",
  CACNEXT20: "CAC Next 20",
  SBF120: "SBF 120",
  AEX: "AEX",
  AMX: "AMX",
  ASCX: "AEX Small Cap",
  BEL20: "BEL 20",
  BELMID: "BEL Mid",
  BELSMALL: "BEL Small",
  PSI: "PSI",
  PSIALL: "PSI All-Share",
  PSIIND: "PSI Industrials",
  ISEQ20: "ISEQ 20",
  ISEQALL: "ISEQ All Share",
  ISEQFIN: "ISEQ Financial",
  DAX40: "DAX 40",
  MDAX: "MDAX",
  TECDAX: "TecDAX",
  FTSE100: "FTSE 100",
  FTSE250: "FTSE 250",
  MSCIUKSC: "MSCI UK Small Cap",
  IBEX35: "IBEX 35",
  IBEXMEDIUM: "IBEX Medium Cap",
  IBEXSMALL: "IBEX Small Cap",
  FTSEMIB: "FTSE MIB",
  FTSEITMID: "FTSE Italia Mid Cap",
  FTSEITSMALL: "FTSE Italia Small Cap",
  DOWJONES: "Dow Jones",
  SP500: "S&P 500",
  NASDAQ100: "Nasdaq-100",
  ATHEXCOMP: "ATHEX Composite",
  ATHEXLARGE: "FTSE/ATHEX Large Cap",
  ATHEXMID: "FTSE/ATHEX Mid Cap",
  SMI: "SMI",
  SMIM: "SMIM",
  SPI: "SPI",
};

export function CompanyUniverse({
  companies,
  scores,
  onExploreIndices,
  onFinancialImport,
  onAnalysis,
  onManage,
  onToggleFavorite,
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
    <section
      className="section"
      id="companies"
      aria-labelledby="universe-title"
    >
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
                        <small key={index}>{INDEX_LABELS[index] ?? index}</small>
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
                      Charger l’historique
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
                  {scoreFor(company) != null && (
                    <button
                      className="row-favorite"
                      data-favorite={company.is_favorite || undefined}
                      onClick={() =>
                        onToggleFavorite(company, !company.is_favorite)
                      }
                      aria-label={
                        company.is_favorite
                          ? `Retirer ${company.name} des favoris`
                          : `Ajouter ${company.name} aux favoris`
                      }
                      title={
                        company.is_favorite
                          ? "Retirer des favoris"
                          : "Ajouter aux favoris"
                      }
                    >
                      <Star
                        aria-hidden="true"
                        size={17}
                        fill={company.is_favorite ? "currentColor" : "none"}
                      />
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
              Sélectionnez une ou plusieurs sociétés depuis un indice boursier.
            </p>
            <button
              className="button button--primary"
              onClick={onExploreIndices}
            >
              <Landmark aria-hidden="true" size={18} />
              Choisir dans les indices
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { FileUp, Inbox, Landmark, Search, Settings2, Star, Trash2 } from "lucide-react";

import type { Company } from "../api/client";

interface CompanyUniverseProps {
  companies: Company[];
  scores: Record<string, number>;
  onExploreIndices: () => void;
  onFinancialImport: (company: Company) => void;
  onAnalysis: (company: Company) => void;
  onManage: (company: Company) => void;
  onToggleFavorite: (company: Company, isFavorite: boolean) => void;
  onDeleteSelected: (companyIds: string[]) => Promise<void>;
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
  onDeleteSelected,
}: CompanyUniverseProps) {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const scoreFor = (company: Company) =>
    scores[company.id] ?? company.latest_mk_score;
  const universeCompanies = useMemo(
    () => companies.filter((company) => !company.is_favorite),
    [companies],
  );
  const filteredCompanies = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");
    if (!normalizedQuery) return universeCompanies;
    return universeCompanies.filter((company) =>
      `${company.name} ${company.ticker}`
        .toLocaleLowerCase("fr")
        .includes(normalizedQuery),
    );
  }, [query, universeCompanies]);
  const filteredIds = useMemo(
    () => filteredCompanies.map((company) => company.id),
    [filteredCompanies],
  );
  const allFilteredSelected = filteredIds.length > 0
    && filteredIds.every((companyId) => selectedIds.has(companyId));
  const someFilteredSelected = filteredIds.some((companyId) => selectedIds.has(companyId));

  useEffect(() => {
    const universeIds = new Set(universeCompanies.map((company) => company.id));
    setSelectedIds((current) => {
      const next = new Set([...current].filter((companyId) => universeIds.has(companyId)));
      return next.size === current.size ? current : next;
    });
  }, [universeCompanies]);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someFilteredSelected && !allFilteredSelected;
    }
  }, [allFilteredSelected, someFilteredSelected]);

  const toggleSelection = (companyId: string) => {
    setConfirmingDelete(false);
    setDeleteError(null);
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(companyId)) next.delete(companyId);
      else next.add(companyId);
      return next;
    });
  };

  const toggleAllFiltered = () => {
    setConfirmingDelete(false);
    setDeleteError(null);
    setSelectedIds((current) => {
      const next = new Set(current);
      filteredIds.forEach((companyId) => {
        if (allFilteredSelected) next.delete(companyId);
        else next.add(companyId);
      });
      return next;
    });
  };

  const deleteSelected = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDeleteSelected([...selectedIds]);
      setSelectedIds(new Set());
      setConfirmingDelete(false);
    } catch (caughtError) {
      setDeleteError(
        caughtError instanceof Error
          ? caughtError.message
          : "La suppression groupée n’a pas pu être effectuée.",
      );
    } finally {
      setDeleting(false);
    }
  };

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
      {selectedIds.size > 0 && (
        <div className="universe-bulk-actions">
          <strong>
            {selectedIds.size} valeur{selectedIds.size > 1 ? "s" : ""} sélectionnée{selectedIds.size > 1 ? "s" : ""}
          </strong>
          {confirmingDelete ? (
            <div className="universe-bulk-confirmation" role="alert">
              <p>
                Supprimer définitivement {selectedIds.size} valeur{selectedIds.size > 1 ? "s" : ""}
                et toutes leurs analyses associées ?
              </p>
              <button
                type="button"
                className="button button--ghost"
                disabled={deleting}
                onClick={() => setConfirmingDelete(false)}
              >
                Annuler
              </button>
              <button
                type="button"
                className="button button--danger"
                disabled={deleting}
                onClick={() => void deleteSelected()}
              >
                <Trash2 aria-hidden="true" size={17} />
                {deleting ? "Suppression…" : "Confirmer la suppression groupée"}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="button button--danger"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 aria-hidden="true" size={17} />
              Supprimer la sélection
            </button>
          )}
          {deleteError && <p className="form-error">{deleteError}</p>}
        </div>
      )}
      <div className="company-table">
        <div className="company-table__head" role="row">
          <label className="company-selection" title="Sélectionner toutes les valeurs affichées">
            <input
              ref={selectAllRef}
              type="checkbox"
              checked={allFilteredSelected}
              disabled={filteredIds.length === 0}
              onChange={toggleAllFiltered}
            />
            <span className="sr-only">Sélectionner toutes les valeurs affichées</span>
          </label>
          <span>Entreprise</span>
          <span>Ticker</span>
          <span>Place de cotation</span>
          <span>Pays</span>
          <span>Statut</span>
        </div>
        {universeCompanies.length ? (
          <div className="company-table__body">
            {filteredCompanies.map((company) => (
              <div
                className="company-table__row"
                data-selected={selectedIds.has(company.id) || undefined}
                role="row"
                key={company.id}
              >
                <label className="company-selection">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(company.id)}
                    onChange={() => toggleSelection(company.id)}
                  />
                  <span className="sr-only">Sélectionner {company.name}</span>
                </label>
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
                  {company.status === "ready" ? (
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
                  ) : company.status === "partial" ? (
                    <div className="company-partial-actions">
                      <button
                        className="company-status company-status--partial company-analysis"
                        onClick={() => onAnalysis(company)}
                        aria-label={`Voir les données disponibles pour ${company.name}`}
                      >
                        <span className="status-dot" aria-hidden="true" />
                        <span>Données partielles</span>
                      </button>
                      <button
                        className="row-manage"
                        onClick={() => onFinancialImport(company)}
                        aria-label={`Réessayer l’import financier pour ${company.name}`}
                        title="Réessayer l’import financier"
                      >
                        <FileUp aria-hidden="true" size={16} />
                      </button>
                    </div>
                  ) : (
                    <button
                      className="company-action"
                      onClick={() => onFinancialImport(company)}
                      aria-label={`Importer les données financières pour ${company.name}`}
                    >
                      <FileUp aria-hidden="true" size={16} />
                      Charger l’historique
                    </button>
                  )}
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
        ) : companies.length ? (
          <div className="empty-state">
            <Star aria-hidden="true" size={40} strokeWidth={1.5} />
            <h3>Toutes les entreprises sont dans vos favoris</h3>
            <p>
              Retirez une entreprise des favoris pour la replacer dans votre
              univers d’investissement.
            </p>
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

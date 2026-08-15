import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, ChevronDown, Search, X } from "lucide-react";

import type {
  CompanyClient,
  IndexBulkAddResult,
  IndexComposition,
  IndexSummary,
} from "../api/client";

interface IndexBrowserDrawerProps {
  client: CompanyClient;
  onComplete(result: IndexBulkAddResult): void;
  onClose(): void;
}

const constituentKey = (company: IndexComposition["constituents"][number]) =>
  company.isin ?? company.ticker ?? company.name;

const regionOrder = ["Europe", "États-Unis", "Chine"];

const byFrenchName = (left: string, right: string) =>
  left.localeCompare(right, "fr", { sensitivity: "base" });

const sectorLabels: Record<string, string> = {
  "Communication Services": "Services de communication",
  "Consumer Discretionary": "Consommation discrétionnaire",
  "Consumer Staples": "Biens de consommation essentiels",
  Energy: "Énergie",
  Financials: "Finance",
  "Health Care": "Santé",
  Industrials: "Industrie",
  "Information Technology": "Technologies de l’information",
  Materials: "Matériaux",
  "Real Estate": "Immobilier",
  Utilities: "Services aux collectivités",
};

const sectorLabel = (sector?: string | null) =>
  (sector && sectorLabels[sector]) || sector || "Autres secteurs";

type IndexGroup = "" | "sector" | "broad";

export function IndexBrowserDrawer({
  client,
  onComplete,
  onClose,
}: IndexBrowserDrawerProps) {
  const [indices, setIndices] = useState<IndexSummary[]>([]);
  const [composition, setComposition] = useState<IndexComposition | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expandedRegion, setExpandedRegion] = useState("Europe");
  const [expandedIndexGroup, setExpandedIndexGroup] =
    useState<IndexGroup>("sector");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadComposition = useCallback(async (code: string) => {
    setLoading(true);
    setError(null);
    setSelected(new Set());
    setQuery("");
    try {
      setComposition(await client.getIndex(code));
    } catch (caughtError) {
      setComposition(null);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La composition de l’indice est indisponible.",
      );
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    let active = true;
    client
      .listIndices()
      .then((items) => {
        if (!active) return;
        setIndices(items);
        const initialIndex =
          items.find(
            (item) =>
              (item.region ?? "Europe") === "Europe" && item.kind === "sector",
          )
          ?? items.find((item) => (item.region ?? "Europe") === "Europe")
          ?? items[0];
        if (initialIndex) {
          setExpandedRegion(initialIndex.region ?? "Europe");
          setExpandedIndexGroup(
            (initialIndex.kind ?? "broad") === "sector" ? "sector" : "broad",
          );
          void loadComposition(initialIndex.code);
        }
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(caughtError instanceof Error ? caughtError.message : "Indices indisponibles.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, loadComposition]);

  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fr");
    if (!normalized) return composition?.constituents ?? [];
    return (composition?.constituents ?? []).filter((item) =>
      `${item.name} ${item.isin ?? ""} ${item.ticker ?? ""}`
        .toLocaleLowerCase("fr")
        .includes(normalized),
    );
  }, [composition, query]);

  const toggle = (isin: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(isin)) next.delete(isin);
      else next.add(isin);
      return next;
    });
  };

  const addSelected = async () => {
    if (!composition || selected.size === 0) return;
    setAdding(true);
    setError(null);
    try {
      const result = await client.addIndexCompanies(
        composition.constituents
          .filter((item) => selected.has(constituentKey(item)))
          .map((item) => ({ ...item, index_code: composition.code })),
      );
      onComplete(result);
      if (result.errors.length === 0) onClose();
      else {
        setSelected(
          new Set(
            result.errors.map(
              (item) => item.isin ?? item.ticker ?? item.name,
            ),
          ),
        );
        setError(
          `${result.created.length + result.existing.length} entreprise(s) ajoutée(s). ` +
            `${result.errors.length} ticker(s) n’ont pas pu être résolus.`,
        );
      }
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Ajout impossible.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button className="drawer-backdrop" onClick={onClose} aria-label="Fermer" />
      <aside
        className="drawer index-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="index-title"
      >
        <header className="drawer__head">
          <div>
            <p className="section-eyebrow">Ajout guidé</p>
            <h2 id="index-title">Explorer un indice boursier</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" size={20} />
          </button>
        </header>
        <div className="index-drawer__body">
          <div className="index-catalog">
            {regionOrder.map((region) => {
              const regionalIndices = indices.filter(
                (index) => (index.region ?? "Europe") === region,
              );
              if (!regionalIndices.length) return null;
              const broadIndices = regionalIndices.filter(
                (index) => (index.kind ?? "broad") === "broad",
              );
              const sectorIndices = regionalIndices.filter(
                (index) => index.kind === "sector",
              );
              const countries = Array.from(
                broadIndices.reduce((groups, index) => {
                  const country = index.country ?? "Non renseigné";
                  groups.set(country, [...(groups.get(country) ?? []), index]);
                  return groups;
                }, new Map<string, IndexSummary[]>()),
              ).sort(([left], [right]) => byFrenchName(left, right));
              const isExpanded = expandedRegion === region;
              const isSectorExpanded = expandedIndexGroup === "sector";
              const isBroadExpanded = expandedIndexGroup === "broad";
              const regionKey = region === "Europe"
                ? "europe"
                : region === "États-Unis"
                  ? "us"
                  : "china";
              return (
                <section key={region} aria-label={`Indices ${region}`}>
                  <button
                    className="index-region-toggle"
                    aria-expanded={isExpanded}
                    onClick={() => {
                      if (isExpanded) {
                        setExpandedRegion("");
                        return;
                      }
                      const nextGroup = sectorIndices.length > 0 ? "sector" : "broad";
                      const nextIndices =
                        nextGroup === "sector" ? sectorIndices : broadIndices;
                      setExpandedRegion(region);
                      setExpandedIndexGroup(nextGroup);
                      if (
                        nextIndices[0]
                        && !nextIndices.some((index) => index.code === composition?.code)
                      ) {
                        void loadComposition(nextIndices[0].code);
                      }
                    }}
                  >
                    <span>{region}</span>
                    <ChevronDown aria-hidden="true" size={18} />
                  </button>
                  {isExpanded && (
                    <div className="index-region-content">
                      {sectorIndices.length > 0 && (
                        <div className="index-catalog-group">
                          <button
                            id={`${regionKey}-sector-toggle`}
                            className="index-group-toggle"
                            aria-expanded={isSectorExpanded}
                            aria-controls={`${regionKey}-sector-panel`}
                            onClick={() => {
                              const nextGroup = isSectorExpanded ? "" : "sector";
                              setExpandedIndexGroup(nextGroup);
                              if (
                                nextGroup
                                && sectorIndices[0]
                                && !sectorIndices.some(
                                  (index) => index.code === composition?.code,
                                )
                              ) {
                                void loadComposition(sectorIndices[0].code);
                              }
                            }}
                          >
                            <span>
                              <strong>Indices sectoriels</strong>
                              <small>
                                {sectorIndices.length} indice
                                {sectorIndices.length > 1 ? "s" : ""} · {region}
                              </small>
                            </span>
                            <ChevronDown aria-hidden="true" size={18} />
                          </button>
                          {isSectorExpanded && (
                            <div
                              id={`${regionKey}-sector-panel`}
                              className="index-sector-grid"
                              role="tablist"
                              aria-label={`Indices sectoriels ${region}`}
                            >
                              {[...sectorIndices]
                                .sort((left, right) => {
                                  const sectorOrder = byFrenchName(
                                    sectorLabel(left.sector),
                                    sectorLabel(right.sector),
                                  );
                                  return (
                                    sectorOrder
                                    || byFrenchName(left.name, right.name)
                                  );
                                })
                                .map((index) => (
                                  <button
                                    key={index.code}
                                    role="tab"
                                    aria-selected={composition?.code === index.code}
                                    onClick={() => {
                                      void loadComposition(index.code);
                                    }}
                                  >
                                    <strong>{sectorLabel(index.sector)}</strong>
                                    <small>{index.name}</small>
                                  </button>
                                ))}
                            </div>
                          )}
                        </div>
                      )}
                      {countries.length > 0 && (
                        <div className="index-catalog-group">
                          <button
                            id={`${regionKey}-broad-toggle`}
                            className="index-group-toggle"
                            aria-expanded={isBroadExpanded}
                            aria-controls={`${regionKey}-broad-panel`}
                            onClick={() => {
                              const nextGroup = isBroadExpanded ? "" : "broad";
                              setExpandedIndexGroup(nextGroup);
                              if (
                                nextGroup
                                && broadIndices[0]
                                && !broadIndices.some(
                                  (index) => index.code === composition?.code,
                                )
                              ) {
                                void loadComposition(broadIndices[0].code);
                              }
                            }}
                          >
                            <span>
                              <strong>Indices généraux</strong>
                              <small>
                                {broadIndices.length} indice
                                {broadIndices.length > 1 ? "s" : ""} · {countries.length} pays
                              </small>
                            </span>
                            <ChevronDown aria-hidden="true" size={18} />
                          </button>
                          {isBroadExpanded && (
                            <div
                              id={`${regionKey}-broad-panel`}
                              className="index-countries"
                              role="region"
                              aria-labelledby={`${regionKey}-broad-toggle`}
                            >
                              {countries.map(([country, countryIndices]) => (
                                <div className="index-country" key={country}>
                                  <span>{country}</span>
                                  <div
                                    className="index-tabs"
                                    role="tablist"
                                    aria-label={`Indices ${country}`}
                                  >
                                    {[...countryIndices]
                                      .sort((left, right) =>
                                        byFrenchName(left.name, right.name),
                                      )
                                      .map((index) => (
                                        <button
                                          key={index.code}
                                          role="tab"
                                          aria-selected={composition?.code === index.code}
                                          onClick={() => {
                                            void loadComposition(index.code);
                                          }}
                                        >
                                          {index.name}
                                        </button>
                                      ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
          <div className="index-toolbar">
            <label className="search-field">
              <Search aria-hidden="true" size={18} />
              <span className="sr-only">Rechercher dans l’indice</span>
              <input
                value={query}
                placeholder="Rechercher une entreprise ou un ISIN"
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <button
              className="button button--ghost"
              disabled={visible.length === 0}
              onClick={() =>
                setSelected((current) => {
                  const allVisible = visible.every((item) =>
                    current.has(constituentKey(item)),
                  );
                  const next = new Set(current);
                  visible.forEach((item) => {
                    const key = constituentKey(item);
                    if (allVisible) next.delete(key);
                    else next.add(key);
                  });
                  return next;
                })
              }
            >
              {visible.every((item) => selected.has(constituentKey(item))) && visible.length
                ? "Désélectionner"
                : "Tout sélectionner"}
            </button>
          </div>
          {composition && (
            <p className="index-meta">
              {composition.constituents.length} composantes
              {composition.kind === "sector" && composition.sector
                ? ` · secteur ${sectorLabel(composition.sector)}`
                : ""}
              {` · composition au ${composition.as_of ?? "dernier relevé"} · source ${composition.provider}`}
            </p>
          )}
          {error && <p className="form-error">{error}</p>}
          {loading ? (
            <p className="index-loading">Chargement de la composition…</p>
          ) : (
            <div className="index-list">
              {visible.length === 0 && composition && (
                <p className="index-empty">
                  {"Aucune entreprise ne correspond \\u00e0 cette recherche."}
                </p>
              )}
              {visible.map((company) => (
                <label className="index-company" key={constituentKey(company)}>
                  <input
                    type="checkbox"
                    checked={selected.has(constituentKey(company))}
                    onChange={() => toggle(constituentKey(company))}
                  />
                  <Building2 aria-hidden="true" size={18} />
                  <span>
                    <strong>{company.name}</strong>
                    <small>
                      {company.ticker ?? company.isin} · {company.trading_location}
                    </small>
                  </span>
                  <small>{company.country}</small>
                </label>
              ))}
            </div>
          )}
        </div>
        <footer className="drawer__actions index-drawer__actions">
          <button className="button button--ghost" onClick={onClose}>Annuler</button>
          <button
            className="button button--primary"
            disabled={selected.size === 0 || adding}
            onClick={() => void addSelected()}
          >
            Ajouter {selected.size || ""} à l’univers
          </button>
        </footer>
      </aside>
    </div>
  );
}

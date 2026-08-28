import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Bot,
  Download,
  LoaderCircle,
  Play,
  RefreshCw,
  SearchCheck,
  Square,
} from "lucide-react";

import type {
  IndexSummary,
  MarketScan,
  MarketScanCriteria,
  MarketScanListItem,
  NationalMarket,
} from "../api/client";

interface MarketScannerProps {
  listIndices(): Promise<IndexSummary[]>;
  listNationalMarkets(): Promise<NationalMarket[]>;
  listScans(): Promise<MarketScanListItem[]>;
  createFromQuestion(question: string): Promise<MarketScan>;
  createScan(criteria: MarketScanCriteria): Promise<MarketScan>;
  getScan(id: string): Promise<MarketScan>;
  retryScan(id: string): Promise<MarketScan>;
  cancelScan(id: string): Promise<MarketScan>;
  exportScan(id: string): Promise<void>;
}

const defaultQuestion =
  "Trouve sur le marché américain les actions ayant baissé d’au moins 80 % sur 5 ans";

const statusLabels = {
  queued: "En attente",
  running: "Analyse en cours",
  completed: "Terminé",
  failed: "À relancer",
  cancelled: "Arrêté",
};

function buildAgentQuestion(
  universe: string,
  options: {
    market: "US" | "INDEX" | "COUNTRY" | "MKVIP";
    years: number;
    direction: "decline" | "gain" | "any";
    threshold: number;
    minimumMarketCapBillions: number | "";
    maximumMarketCapBillions: number | "";
    maximumPe: number | "";
    maximumPriceToBook: number | "";
    minimumDividendYield: number | "";
    minimumMkScore: number | "";
    minimumAnnualizedReturn: number | "";
    maximumVolatility: number | "";
    minimumDrawdown: number | "";
    sortBy: MarketScanCriteria["sort_by"];
    sortDirection: MarketScanCriteria["sort_direction"];
    resultLimit: number | "";
  },
) {
  const scope = options.market === "INDEX"
    ? `dans l’indice ${universe}`
    : options.market === "COUNTRY"
      ? `sur le marché national de ${universe}`
      : options.market === "MKVIP"
        ? "dans mon univers MK-VIP"
      : "sur le marché américain";
  const movement = options.direction === "decline"
    ? ` ayant baissé d’au moins ${options.threshold.toLocaleString("fr-FR")} %`
    : options.direction === "gain"
      ? ` ayant progressé d’au moins ${options.threshold.toLocaleString("fr-FR")} %`
      : "";
  const filters = [
    options.minimumMarketCapBillions !== "" && options.minimumMarketCapBillions > 0
      ? `une capitalisation d’au moins ${options.minimumMarketCapBillions.toLocaleString("fr-FR")} milliard${options.minimumMarketCapBillions > 1 ? "s" : ""}`
      : null,
    options.maximumMarketCapBillions !== "" && options.maximumMarketCapBillions > 0
      ? `une capitalisation d’au plus ${options.maximumMarketCapBillions.toLocaleString("fr-FR")} milliard${options.maximumMarketCapBillions > 1 ? "s" : ""}`
      : null,
    options.maximumPe !== "" ? `un PER inférieur à ${options.maximumPe}` : null,
    options.maximumPriceToBook !== "" ? `un P/B inférieur à ${options.maximumPriceToBook}` : null,
    options.minimumDividendYield !== "" ? `un rendement du dividende d’au moins ${options.minimumDividendYield} %` : null,
    options.minimumMkScore !== "" ? `un MK Score d’au moins ${options.minimumMkScore}` : null,
    options.minimumAnnualizedReturn !== "" ? `un rendement annualisé d’au moins ${options.minimumAnnualizedReturn} %` : null,
    options.maximumVolatility !== "" ? `une volatilité d’au plus ${options.maximumVolatility} %` : null,
    options.minimumDrawdown !== "" ? `un drawdown d’au moins ${options.minimumDrawdown} %` : null,
  ].filter(Boolean);
  const filterText = filters.length ? `, avec ${filters.join(", ")}` : "";
  const rankingLabels: Record<MarketScanCriteria["sort_by"], string> = {
    performance: "performance",
    annualized_return: "rendement annualisé",
    volatility: "volatilité",
    max_drawdown: "drawdown maximal",
    market_cap: "capitalisation",
    pe_ratio: "PER",
    price_to_book: "cours/actif net",
    dividend_yield: "rendement du dividende",
    mk_score: "MK Score",
  };
  const ranking = options.sortBy !== "performance" || options.resultLimit !== ""
    ? `, classées par ${rankingLabels[options.sortBy]} ${options.sortDirection === "desc" ? "décroissant" : "croissant"}${options.resultLimit !== "" ? `, top ${options.resultLimit}` : ""}`
    : "";
  return `Trouve ${scope} les actions${movement} sur ${options.years} an${options.years > 1 ? "s" : ""}${filterText}${ranking}`;
}

function optionalNumber(value: string): number | "" {
  return value === "" ? "" : Number(value);
}

function formatRatio(value: number | null, suffix = "") {
  return value === null ? "—" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}${suffix}`;
}

function formatMarketCap(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("fr-FR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function MarketScanner({
  listIndices,
  listNationalMarkets,
  listScans,
  createFromQuestion,
  createScan,
  getScan,
  retryScan,
  cancelScan,
  exportScan,
}: MarketScannerProps) {
  const [question, setQuestion] = useState(defaultQuestion);
  const [market, setMarket] = useState<"US" | "INDEX" | "COUNTRY" | "MKVIP">("US");
  const [indexCode, setIndexCode] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [indices, setIndices] = useState<IndexSummary[]>([]);
  const [nationalMarkets, setNationalMarkets] = useState<NationalMarket[]>([]);
  const [years, setYears] = useState(5);
  const [performanceDirection, setPerformanceDirection] = useState<"decline" | "gain" | "any">("decline");
  const [threshold, setThreshold] = useState(80);
  const [minimumMarketCapBillions, setMinimumMarketCapBillions] = useState<number | "">("");
  const [maximumMarketCapBillions, setMaximumMarketCapBillions] = useState<number | "">("");
  const [maximumPe, setMaximumPe] = useState<number | "">("");
  const [maximumPriceToBook, setMaximumPriceToBook] = useState<number | "">("");
  const [minimumDividendYield, setMinimumDividendYield] = useState<number | "">("");
  const [minimumMkScore, setMinimumMkScore] = useState<number | "">("");
  const [minimumAnnualizedReturn, setMinimumAnnualizedReturn] = useState<number | "">("");
  const [maximumVolatility, setMaximumVolatility] = useState<number | "">("");
  const [minimumDrawdown, setMinimumDrawdown] = useState<number | "">("");
  const [sortBy, setSortBy] = useState<MarketScanCriteria["sort_by"]>("performance");
  const [sortDirection, setSortDirection] = useState<MarketScanCriteria["sort_direction"]>("asc");
  const [resultLimit, setResultLimit] = useState<number | "">("");
  const [scans, setScans] = useState<MarketScanListItem[]>([]);
  const [selected, setSelected] = useState<MarketScan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const running = selected?.status === "queued" || selected?.status === "running";
  const selectedId = selected?.id;
  const displayedResults = useMemo(() => selected?.results.slice(0, 100) ?? [], [selected]);
  const indexGroups = useMemo(() => {
    const groups = new Map<string, IndexSummary[]>();
    for (const index of indices) {
      const label = `${index.region ?? "Autre"} · ${index.country ?? "Non renseigné"}`;
      groups.set(label, [...(groups.get(label) ?? []), index]);
    }
    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right, "fr"))
      .map(([label, items]) => [
        label,
        items.sort((left, right) => left.name.localeCompare(right.name, "fr")),
      ] as const);
  }, [indices]);
  const countryGroups = useMemo(() => {
    const groups = new Map<string, NationalMarket[]>();
    for (const item of nationalMarkets) {
      groups.set(item.region, [...(groups.get(item.region) ?? []), item]);
    }
    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right, "fr"))
      .map(([label, items]) => [
        label,
        items.sort((left, right) => left.name.localeCompare(right.name, "fr")),
      ] as const);
  }, [nationalMarkets]);
  const selectedCountry = nationalMarkets.find((item) => item.code === countryCode);
  const resultCountry = nationalMarkets.find(
    (item) => item.code === selected?.criteria.country_code,
  );
  const selectedUniverse = selected?.criteria.market === "INDEX"
    ? indices.find((index) => index.code === selected.criteria.index_code)?.name
      ?? selected.criteria.index_code
      ?? "Indice MK-VIP"
    : selected?.criteria.market === "COUNTRY"
      ? `Marché national — ${resultCountry?.name ?? selected.criteria.country_code ?? "Pays"}`
      : selected?.criteria.market === "MKVIP"
        ? "Univers d’investissement MK-VIP"
      : "Marché américain";
  const researchUniverse = market === "INDEX"
    ? indices.find((index) => index.code === indexCode)?.name ?? indexCode ?? "Indice MK-VIP"
    : market === "COUNTRY"
      ? selectedCountry?.name ?? "Marché national"
      : market === "MKVIP"
        ? "Univers MK-VIP"
      : "Marché américain";

  useEffect(() => {
    setQuestion(
      buildAgentQuestion(
        researchUniverse,
        {
          market,
          years,
          direction: performanceDirection,
          threshold,
          minimumMarketCapBillions,
          maximumMarketCapBillions,
          maximumPe,
          maximumPriceToBook,
          minimumDividendYield,
          minimumMkScore,
          minimumAnnualizedReturn,
          maximumVolatility,
          minimumDrawdown,
          sortBy,
          sortDirection,
          resultLimit,
        },
      ),
    );
  }, [market, maximumMarketCapBillions, maximumPe, maximumPriceToBook,
    maximumVolatility, minimumAnnualizedReturn, minimumDividendYield,
    minimumDrawdown, minimumMarketCapBillions, minimumMkScore,
    performanceDirection, researchUniverse, resultLimit, sortBy, sortDirection,
    threshold, years]);

  const refreshList = async () => {
    const history = await listScans();
    setScans(history);
    return history;
  };

  useEffect(() => {
    let active = true;
    listScans()
      .then(async (history) => {
        if (!active) return;
        setScans(history);
        if (history[0]) setSelected(await getScan(history[0].id));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [getScan, listScans]);

  useEffect(() => {
    let active = true;
    listIndices()
      .then((catalog) => {
        if (!active) return;
        setIndices(catalog);
        setIndexCode((current) => current || catalog[0]?.code || "");
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [listIndices]);

  useEffect(() => {
    let active = true;
    listNationalMarkets()
      .then((catalog) => {
        if (!active) return;
        setNationalMarkets(catalog);
        setCountryCode((current) => current || catalog[0]?.code || "");
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [listNationalMarkets]);

  useEffect(() => {
    if (!running || !selectedId) return;
    const timer = window.setInterval(() => {
      getScan(selectedId)
        .then(async (scan) => {
          setSelected(scan);
          if (scan.status === "completed" || scan.status === "failed") {
            setScans(await listScans());
          }
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [getScan, listScans, running, selectedId]);

  const start = async (action: () => Promise<MarketScan>) => {
    setBusy(true);
    setError(null);
    try {
      const scan = await action();
      setSelected(scan);
      await refreshList();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Le scan n’a pas pu démarrer.");
    } finally {
      setBusy(false);
    }
  };

  const submitQuestion = (event: FormEvent) => {
    event.preventDefault();
    void start(() => createFromQuestion(question.trim()));
  };

  const submitCriteria = () => {
    void start(() =>
      createScan({
        market,
        index_code: market === "INDEX" ? indexCode : null,
        country_code: market === "COUNTRY" ? countryCode : null,
        exchanges: ["NASDAQ", "NYSE", "AMEX"],
        years,
        performance_direction: performanceDirection,
        minimum_decline_pct: threshold,
        minimum_market_cap: minimumMarketCapBillions !== "" &&
          minimumMarketCapBillions > 0 ? minimumMarketCapBillions * 1_000_000_000 : null,
        maximum_market_cap: maximumMarketCapBillions !== "" &&
          maximumMarketCapBillions > 0 ? maximumMarketCapBillions * 1_000_000_000 : null,
        maximum_pe_ratio: maximumPe === "" ? null : maximumPe,
        maximum_price_to_book: maximumPriceToBook === "" ? null : maximumPriceToBook,
        minimum_dividend_yield_pct: minimumDividendYield === "" ? null : minimumDividendYield,
        minimum_mk_score: minimumMkScore === "" ? null : minimumMkScore,
        minimum_annualized_return_pct: minimumAnnualizedReturn === "" ? null : minimumAnnualizedReturn,
        maximum_volatility_pct: maximumVolatility === "" ? null : maximumVolatility,
        minimum_drawdown_pct: minimumDrawdown === "" ? null : minimumDrawdown,
        sort_by: sortBy,
        sort_direction: sortDirection,
        result_limit: resultLimit === "" ? null : resultLimit,
        ordinary_shares_only: true,
      }),
    );
  };

  const stop = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const scan = await cancelScan(selectedId);
      setSelected(scan);
      setQuestion(
        buildAgentQuestion(
          researchUniverse,
          {
            market,
            years,
            direction: performanceDirection,
            threshold,
            minimumMarketCapBillions,
            maximumMarketCapBillions,
            maximumPe,
            maximumPriceToBook,
            minimumDividendYield,
            minimumMkScore,
            minimumAnnualizedReturn,
            maximumVolatility,
            minimumDrawdown,
            sortBy,
            sortDirection,
            resultLimit,
          },
        ),
      );
      await refreshList();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "L’analyse n’a pas pu être arrêtée.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="section market-scanner" id="market-scanner" aria-labelledby="market-scan-title">
      <div className="market-scanner__head">
        <div>
          <p className="section-eyebrow"><Bot aria-hidden="true" size={17} /> Agent IA</p>
          <h2 id="market-scan-title">Moteur de sélection d’actions MK-VIP</h2>
          <p>
            L’agent combine performance, risque, valorisation, dividende, capitalisation et MK Score
            sur les marchés complets, les indices ou votre univers d’investissement.
          </p>
        </div>
        <SearchCheck aria-hidden="true" size={34} />
      </div>

      <form className="market-scanner__prompt" onSubmit={submitQuestion}>
        <label className="field">
          <span>Demande à l’agent</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            minLength={5}
            maxLength={800}
            required
          />
        </label>
        <button className="button button--primary" disabled={busy || running}>
          {busy ? <LoaderCircle className="ai-loading" aria-hidden="true" size={18} /> : <Play aria-hidden="true" size={18} />}
          Lancer avec l’agent
        </button>
      </form>

      <details className="market-scanner__advanced">
        <summary>Critères manuels</summary>
        <div className="market-scanner__criteria">
          <label className="field">
            <span>Univers de la recherche</span>
            <select value={market} onChange={(event) => setMarket(event.target.value as "US" | "INDEX" | "COUNTRY" | "MKVIP")}>
              <option value="US">Marché américain complet</option>
              <option value="COUNTRY">Un autre marché national complet</option>
              <option value="INDEX">Un indice MK-VIP</option>
              <option value="MKVIP">Mon univers d’investissement MK-VIP</option>
            </select>
          </label>
          {market === "INDEX" && (
            <label className="field market-scanner__index-field">
              <span>Indice</span>
              <select value={indexCode} onChange={(event) => setIndexCode(event.target.value)} required>
                {indexGroups.map(([label, items]) => (
                  <optgroup label={label} key={label}>
                    {items.map((index) => (
                      <option key={index.code} value={index.code}>
                        {index.name} · {index.kind === "sector" ? "sectoriel" : "général"}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
          )}
          {market === "COUNTRY" && (
            <label className="field market-scanner__index-field">
              <span>Pays</span>
              <select value={countryCode} onChange={(event) => setCountryCode(event.target.value)} required>
                {countryGroups.map(([label, items]) => (
                  <optgroup label={label} key={label}>
                    {items.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.name} · {item.currency}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
          )}
          <label className="field">
            <span>Période</span>
            <select value={years} onChange={(event) => setYears(Number(event.target.value))}>
              {[1, 3, 5, 7, 10].map((value) => <option key={value} value={value}>{value} ans</option>)}
            </select>
          </label>
          <label className="field">
            <span>Mouvement du cours</span>
            <select
              value={performanceDirection}
              onChange={(event) => {
                const direction = event.target.value as "decline" | "gain" | "any";
                setPerformanceDirection(direction);
                setSortBy("performance");
                setSortDirection(direction === "gain" ? "desc" : "asc");
              }}
            >
              <option value="decline">Baisse minimale</option>
              <option value="gain">Hausse minimale</option>
              <option value="any">Indifférent</option>
            </select>
          </label>
          {performanceDirection !== "any" && (
            <label className="field">
              <span>Amplitude minimale (%)</span>
              <input type="number" min="0" max="100000" step="0.1" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
            </label>
          )}
          <label className="field">
            <span>Capitalisation minimale (Md)</span>
            <input type="number" min="0" step="0.1" value={minimumMarketCapBillions} onChange={(event) => setMinimumMarketCapBillions(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Capitalisation maximale (Md)</span>
            <input type="number" min="0" step="0.1" value={maximumMarketCapBillions} onChange={(event) => setMaximumMarketCapBillions(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>PER maximal</span>
            <input type="number" min="0.1" step="0.1" value={maximumPe} onChange={(event) => setMaximumPe(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Cours / actif net maximal</span>
            <input type="number" min="0.1" step="0.1" value={maximumPriceToBook} onChange={(event) => setMaximumPriceToBook(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Rendement du dividende minimal (%)</span>
            <input type="number" min="0" max="100" step="0.1" value={minimumDividendYield} onChange={(event) => setMinimumDividendYield(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>MK Score minimal</span>
            <input type="number" min="0" max="100" step="0.1" value={minimumMkScore} onChange={(event) => setMinimumMkScore(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Rendement annualisé minimal (%)</span>
            <input type="number" min="-100" step="0.1" value={minimumAnnualizedReturn} onChange={(event) => setMinimumAnnualizedReturn(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Volatilité maximale (%)</span>
            <input type="number" min="0" step="0.1" value={maximumVolatility} onChange={(event) => setMaximumVolatility(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Drawdown minimal (%)</span>
            <input type="number" min="0" max="100" step="0.1" value={minimumDrawdown} onChange={(event) => setMinimumDrawdown(optionalNumber(event.target.value))} />
          </label>
          <label className="field">
            <span>Classer par</span>
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as MarketScanCriteria["sort_by"])}>
              <option value="performance">Performance</option>
              <option value="annualized_return">Rendement annualisé</option>
              <option value="volatility">Volatilité</option>
              <option value="max_drawdown">Drawdown maximal</option>
              <option value="market_cap">Capitalisation</option>
              <option value="pe_ratio">PER</option>
              <option value="price_to_book">Cours / actif net</option>
              <option value="dividend_yield">Rendement du dividende</option>
              <option value="mk_score">MK Score</option>
            </select>
          </label>
          <label className="field">
            <span>Ordre</span>
            <select value={sortDirection} onChange={(event) => setSortDirection(event.target.value as "asc" | "desc")}>
              <option value="asc">Croissant</option>
              <option value="desc">Décroissant</option>
            </select>
          </label>
          <label className="field">
            <span>Nombre maximal de résultats</span>
            <input type="number" min="1" max="1000" step="1" value={resultLimit} onChange={(event) => setResultLimit(optionalNumber(event.target.value))} />
          </label>
          <button className="button button--secondary" type="button" disabled={busy || running || (market === "INDEX" && !indexCode) || (market === "COUNTRY" && !countryCode)} onClick={submitCriteria}>Lancer ces critères</button>
        </div>
      </details>

      {error && <p className="form-error" role="alert">{error}</p>}

      {selected && (
        <div className="market-scan-result" aria-live="polite">
          <div className="market-scan-result__status">
            <div>
              <span className={`market-scan-status market-scan-status--${selected.status}`}>
                {statusLabels[selected.status]}
              </span>
              <strong>{selected.progress_pct.toLocaleString("fr-FR")} %</strong>
              <small>
                {selected.processed_securities.toLocaleString("fr-FR")} / {selected.total_securities.toLocaleString("fr-FR")} valeurs
              </small>
            </div>
            <div className="market-scan-result__actions">
              {running && (
                <button className="button button--secondary" disabled={busy} onClick={() => void stop()}>
                  <Square aria-hidden="true" size={16} /> Arrêter l’analyse
                </button>
              )}
              {selected.status === "failed" && (
                <button className="button button--secondary" onClick={() => void start(() => retryScan(selected.id))}>
                  <RefreshCw aria-hidden="true" size={17} /> Relancer
                </button>
              )}
              {selected.status === "completed" && (
                <button className="button button--secondary" onClick={() => void exportScan(selected.id)}>
                  <Download aria-hidden="true" size={17} /> Télécharger Excel
                </button>
              )}
            </div>
          </div>
          <div className="market-scan-progress" aria-label={`Progression ${selected.progress_pct} %`}>
            <span style={{ width: `${selected.progress_pct}%` }} />
          </div>
          <dl className="market-scan-summary">
            <div><dt>Résultats</dt><dd>{selected.matched_securities}</dd></div>
            <div><dt>Univers analysé</dt><dd>{selectedUniverse}</dd></div>
            <div><dt>Période</dt><dd>{selected.criteria.years} ans</dd></div>
            <div><dt>Mouvement</dt><dd>{selected.criteria.performance_direction === "decline" ? "Baisse" : selected.criteria.performance_direction === "gain" ? "Hausse" : "Indifférent"}{selected.criteria.performance_direction !== "any" ? ` ≥ ${selected.criteria.minimum_decline_pct} %` : ""}</dd></div>
            <div><dt>Historiques insuffisants</dt><dd>{selected.insufficient_history_securities}</dd></div>
          </dl>
          {selected.error_message && <p className="form-error">{selected.error_message}</p>}

          {displayedResults.length > 0 && (
            <div className="market-scan-table-wrap">
              <table className="market-scan-table">
                <thead><tr><th>Place</th><th>Valeur</th><th>Capitalisation</th><th>PER</th><th>P/B</th><th>Dividende</th><th>MK Score</th><th>Performance</th><th>Annualisée</th><th>Volatilité</th><th>Drawdown</th></tr></thead>
                <tbody>
                  {displayedResults.map((item) => (
                    <tr key={item.id}>
                      <td>{item.exchange}</td>
                      <td><strong>{item.ticker}</strong><span>{item.name}</span></td>
                      <td>{formatMarketCap(item.market_cap)}</td>
                      <td>{formatRatio(item.pe_ratio)}</td>
                      <td>{formatRatio(item.price_to_book)}</td>
                      <td>{formatRatio(item.dividend_yield_pct, " %")}</td>
                      <td>{formatRatio(item.mk_score)}</td>
                      <td className="market-scan-loss">{item.performance_pct.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} %</td>
                      <td>{formatRatio(item.annualized_return_pct, " %")}</td>
                      <td>{formatRatio(item.volatility_pct, " %")}</td>
                      <td>{formatRatio(item.max_drawdown_pct, " %")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.results.length > 100 && <p className="market-scan-note">Les 100 premiers résultats du classement sont affichés. Le fichier Excel contient les {selected.results.length} résultats retenus.</p>}
            </div>
          )}
        </div>
      )}

      {scans.length > 1 && (
        <label className="field market-scanner__history">
          <span>Scans précédents</span>
          <select value={selected?.id ?? ""} onChange={(event) => void getScan(event.target.value).then(setSelected)}>
            {scans.map((scan) => (
              <option value={scan.id} key={scan.id}>
                {new Date(scan.created_at).toLocaleString("fr-FR")} · {scan.criteria.index_code ?? nationalMarkets.find((item) => item.code === scan.criteria.country_code)?.name ?? (scan.criteria.market === "MKVIP" ? "Univers MK-VIP" : "Marché US")} · {statusLabels[scan.status]} · {scan.matched_securities} résultats
              </option>
            ))}
          </select>
        </label>
      )}
      <p className="market-scan-note">
        Les critères fondamentaux ne retiennent que les valeurs disposant du ratio demandé. Le MK Score est disponible pour les entreprises déjà analysées dans MK-VIP. Les cours ajustés sont privilégiés pour tenir compte des opérations sur titres.
      </p>
    </section>
  );
}

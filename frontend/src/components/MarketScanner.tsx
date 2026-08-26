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
  market: "US" | "INDEX" | "COUNTRY",
  years: number,
  decline: number,
  minimumMarketCapBillions: number,
) {
  const scope = market === "INDEX"
    ? `dans l’indice ${universe}`
    : market === "COUNTRY"
      ? `sur le marché national de ${universe}`
      : "sur le marché américain";
  const marketCap = market !== "INDEX" && minimumMarketCapBillions > 0
    ? ` avec une capitalisation d’au moins ${minimumMarketCapBillions.toLocaleString("fr-FR")} milliard${minimumMarketCapBillions > 1 ? "s" : ""} en devise locale`
    : "";
  return `Trouve ${scope} les actions ayant baissé d’au moins ${decline.toLocaleString("fr-FR")} % sur ${years} an${years > 1 ? "s" : ""}${marketCap}`;
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
  const [market, setMarket] = useState<"US" | "INDEX" | "COUNTRY">("US");
  const [indexCode, setIndexCode] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [indices, setIndices] = useState<IndexSummary[]>([]);
  const [nationalMarkets, setNationalMarkets] = useState<NationalMarket[]>([]);
  const [years, setYears] = useState(5);
  const [decline, setDecline] = useState(80);
  const [minimumMarketCapBillions, setMinimumMarketCapBillions] = useState(0);
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
      : "Marché américain";
  const researchUniverse = market === "INDEX"
    ? indices.find((index) => index.code === indexCode)?.name ?? indexCode ?? "Indice MK-VIP"
    : market === "COUNTRY"
      ? selectedCountry?.name ?? "Marché national"
      : "Marché américain";

  useEffect(() => {
    setQuestion(
      buildAgentQuestion(
        researchUniverse,
        market,
        years,
        decline,
        minimumMarketCapBillions,
      ),
    );
  }, [decline, market, minimumMarketCapBillions, researchUniverse, years]);

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
        minimum_decline_pct: decline,
        minimum_market_cap: market !== "INDEX" &&
          minimumMarketCapBillions > 0 ? minimumMarketCapBillions * 1_000_000_000 : null,
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
          market,
          years,
          decline,
          minimumMarketCapBillions,
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
          <h2 id="market-scan-title">Scan des marchés nationaux et indices MK-VIP</h2>
          <p>
            L’agent transforme votre demande en critères vérifiés, puis examine un marché national
            complet ou les composantes de l’un des indices disponibles dans MK-VIP.
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
            <select value={market} onChange={(event) => setMarket(event.target.value as "US" | "INDEX" | "COUNTRY")}>
              <option value="US">Marché américain complet</option>
              <option value="COUNTRY">Un autre marché national complet</option>
              <option value="INDEX">Un indice MK-VIP</option>
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
            <span>Baisse minimale</span>
            <input type="number" min="1" max="99.9" step="0.1" value={decline} onChange={(event) => setDecline(Number(event.target.value))} />
          </label>
          {market !== "INDEX" && (
            <label className="field">
              <span>Capitalisation minimale (Md, devise locale)</span>
              <input type="number" min="0" step="0.1" value={minimumMarketCapBillions} onChange={(event) => setMinimumMarketCapBillions(Number(event.target.value))} />
            </label>
          )}
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
            <div><dt>Baisse</dt><dd>≥ {selected.criteria.minimum_decline_pct} %</dd></div>
            <div><dt>Historiques insuffisants</dt><dd>{selected.insufficient_history_securities}</dd></div>
          </dl>
          {selected.error_message && <p className="form-error">{selected.error_message}</p>}

          {displayedResults.length > 0 && (
            <div className="market-scan-table-wrap">
              <table className="market-scan-table">
                <thead><tr><th>Place</th><th>Valeur</th><th>Capitalisation</th><th>Départ</th><th>Fin</th><th>Performance</th></tr></thead>
                <tbody>
                  {displayedResults.map((item) => (
                    <tr key={item.id}>
                      <td>{item.exchange}</td>
                      <td><strong>{item.ticker}</strong><span>{item.name}</span></td>
                      <td>{formatMarketCap(item.market_cap)}</td>
                      <td>{item.start_price.toLocaleString("fr-FR", { maximumFractionDigits: 4 })}<small>{item.start_date}</small></td>
                      <td>{item.end_price.toLocaleString("fr-FR", { maximumFractionDigits: 4 })}<small>{item.end_date}</small></td>
                      <td className="market-scan-loss">{item.performance_pct.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} %</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.results.length > 100 && <p className="market-scan-note">Les 100 plus fortes baisses sont affichées. Le fichier Excel contient les {selected.results.length} résultats.</p>}
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
                {new Date(scan.created_at).toLocaleString("fr-FR")} · {scan.criteria.index_code ?? nationalMarkets.find((item) => item.code === scan.criteria.country_code)?.name ?? "Marché US"} · {statusLabels[scan.status]} · {scan.matched_securities} résultats
              </option>
            ))}
          </select>
        </label>
      )}
      <p className="market-scan-note">
        Périmètre : actions actuellement cotées sur les places nationales principales, avec une capitalisation publiée, et compositions d’indices disponibles dans MK-VIP. Les titres retirés de la cote ne figurent pas dans les univers publics courants. Les cours ajustés sont privilégiés pour tenir compte des opérations sur titres.
      </p>
    </section>
  );
}

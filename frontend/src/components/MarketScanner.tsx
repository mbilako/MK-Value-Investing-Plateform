import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Bot,
  Download,
  LoaderCircle,
  Play,
  RefreshCw,
  SearchCheck,
} from "lucide-react";

import type {
  MarketScan,
  MarketScanCriteria,
  MarketScanListItem,
} from "../api/client";

interface MarketScannerProps {
  listScans(): Promise<MarketScanListItem[]>;
  createFromQuestion(question: string): Promise<MarketScan>;
  createScan(criteria: MarketScanCriteria): Promise<MarketScan>;
  getScan(id: string): Promise<MarketScan>;
  retryScan(id: string): Promise<MarketScan>;
  exportScan(id: string): Promise<void>;
}

const defaultQuestion =
  "Trouve sur le marché américain les actions ayant baissé d’au moins 80 % sur 5 ans";

const statusLabels = {
  queued: "En attente",
  running: "Analyse en cours",
  completed: "Terminé",
  failed: "À relancer",
};

function formatMarketCap(value: number | null) {
  if (value === null) return "—";
  return new Intl.NumberFormat("fr-FR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function MarketScanner({
  listScans,
  createFromQuestion,
  createScan,
  getScan,
  retryScan,
  exportScan,
}: MarketScannerProps) {
  const [question, setQuestion] = useState(defaultQuestion);
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
        market: "US",
        exchanges: ["NASDAQ", "NYSE", "AMEX"],
        years,
        minimum_decline_pct: decline,
        minimum_market_cap:
          minimumMarketCapBillions > 0 ? minimumMarketCapBillions * 1_000_000_000 : null,
        ordinary_shares_only: true,
      }),
    );
  };

  return (
    <section className="section market-scanner" id="market-scanner" aria-labelledby="market-scan-title">
      <div className="market-scanner__head">
        <div>
          <p className="section-eyebrow"><Bot aria-hidden="true" size={17} /> Agent IA</p>
          <h2 id="market-scan-title">Scan du marché américain</h2>
          <p>
            L’agent transforme votre demande en critères vérifiés, puis le moteur examine les
            actions ordinaires du NASDAQ, du NYSE et de l’AMEX en arrière-plan.
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
            <span>Période</span>
            <select value={years} onChange={(event) => setYears(Number(event.target.value))}>
              {[1, 3, 5, 7, 10].map((value) => <option key={value} value={value}>{value} ans</option>)}
            </select>
          </label>
          <label className="field">
            <span>Baisse minimale</span>
            <input type="number" min="1" max="99.9" step="0.1" value={decline} onChange={(event) => setDecline(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>Capitalisation minimale (Md$)</span>
            <input type="number" min="0" step="0.1" value={minimumMarketCapBillions} onChange={(event) => setMinimumMarketCapBillions(Number(event.target.value))} />
          </label>
          <button className="button button--secondary" type="button" disabled={busy || running} onClick={submitCriteria}>Lancer ces critères</button>
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
                {new Date(scan.created_at).toLocaleString("fr-FR")} · {statusLabels[scan.status]} · {scan.matched_securities} résultats
              </option>
            ))}
          </select>
        </label>
      )}
      <p className="market-scan-note">
        Périmètre : sociétés actuellement cotées. Les titres retirés de la cote ne figurent pas dans l’univers public courant. Les cours ajustés sont privilégiés pour tenir compte des opérations sur titres.
      </p>
    </section>
  );
}

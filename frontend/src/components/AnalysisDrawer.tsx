import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { useEffect, useState } from "react";

import type {
  Company,
  FinancialAnalysis,
  FinancialHistory,
  ScoringAnalysis,
  ScoringPayload,
  ValuationAnalysis,
  ValuationPayload,
} from "../api/client";
import { ScorePanel } from "./ScorePanel";
import { ValuationPanel } from "./ValuationPanel";

interface AnalysisDrawerProps {
  company: Company;
  history: FinancialHistory | null;
  valuations: ValuationAnalysis[];
  scores: ScoringAnalysis[];
  loading: boolean;
  error: string | null;
  onCreateValuation: (payload: ValuationPayload) => Promise<ValuationAnalysis>;
  onCreateScore: (payload: ScoringPayload) => Promise<ScoringAnalysis>;
  onClose: () => void;
}

type FundamentalKey =
  | "revenue"
  | "net_income"
  | "pretax_income"
  | "operating_income"
  | "shares_outstanding"
  | "market_cap"
  | "total_equity"
  | "operating_cash_flow"
  | "investing_cash_flow"
  | "closing_price"
  | "pe_ratio"
  | "equity_value_per_share";

type TrendKey =
  | "revenue"
  | "net_income"
  | "operating_income"
  | "pretax_income"
  | "pe_ratio"
  | "roe"
  | "current_ratio";

type HistoryColumnKey =
  | "fiscal_year"
  | "revenue"
  | "net_income"
  | "operating_income"
  | "pretax_income"
  | "closing_price"
  | "pe_ratio"
  | "roe"
  | "equity_to_assets"
  | "operating_cash_flow"
  | "mk_score";

const FUNDAMENTAL_ORDER: FundamentalKey[] = [
  "revenue",
  "net_income",
  "pretax_income",
  "operating_income",
  "shares_outstanding",
  "market_cap",
  "total_equity",
  "operating_cash_flow",
  "investing_cash_flow",
  "closing_price",
  "pe_ratio",
  "equity_value_per_share",
];

const TREND_ORDER: TrendKey[] = [
  "revenue",
  "net_income",
  "operating_income",
  "pretax_income",
  "pe_ratio",
  "roe",
  "current_ratio",
];

const HISTORY_ORDER: HistoryColumnKey[] = [
  "fiscal_year",
  "revenue",
  "net_income",
  "operating_income",
  "pretax_income",
  "closing_price",
  "pe_ratio",
  "roe",
  "equity_to_assets",
  "operating_cash_flow",
  "mk_score",
];

const FUNDAMENTAL_LABELS: Record<FundamentalKey, string> = {
  revenue: "Revenus publiés",
  net_income: "Résultat net",
  pretax_income: "Résultat avant impôt",
  operating_income: "Résultat d’exploitation",
  shares_outstanding: "Actions en circulation",
  market_cap: "Capitalisation boursière",
  total_equity: "Capitaux propres",
  operating_cash_flow: "Flux de trésorerie d’exploitation",
  investing_cash_flow: "Flux de trésorerie d’investissement",
  closing_price: "Dernier cours de bourse au 31 décembre",
  pe_ratio: "Cours / bénéfice (PER)",
  equity_value_per_share: "Valeur économique des capitaux propres par action",
};

const TREND_LABELS: Record<TrendKey, string> = {
  revenue: "Revenus",
  net_income: "Résultat net",
  operating_income: "Résultat d’exploitation",
  pretax_income: "Résultat avant impôt",
  pe_ratio: "Cours / bénéfice (PER)",
  roe: "Rendement des capitaux propres (ROE)",
  current_ratio: "Actif circulant / passif exigible",
};

const HISTORY_LABELS: Record<HistoryColumnKey, string> = {
  fiscal_year: "Exercice",
  revenue: "Revenus",
  net_income: "Résultat net",
  operating_income: "Résultat d’exploitation",
  pretax_income: "Résultat avant impôt",
  closing_price: "Cours de clôture",
  pe_ratio: "PER",
  roe: "ROE",
  equity_to_assets: "Fonds propres / actif",
  operating_cash_flow: "Cash-flow d’exploitation",
  mk_score: "MK Score",
};

function formatAmount(value: number | null | undefined, currency: string): string {
  if (value == null) return "N/A";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M ${currency}`;
}

function formatShares(value: number | null | undefined): string {
  if (value == null) return "N/A";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} M actions`;
}

function formatPrice(value: number | null | undefined, currency: string): string {
  if (value == null) return "N/A";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} ${currency}`;
}

function ratio(numerator: number | null | undefined, denominator: number | null | undefined) {
  if (numerator == null || denominator == null || denominator <= 0) return null;
  return numerator / denominator;
}

function formatRatio(value: number | null): string {
  if (value == null) return "N/A";
  return `${(value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

function formatMultiple(value: number | null): string {
  if (value == null) return "N/A";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}×`;
}

function formatGrowth(value: number | null | undefined): string {
  if (value == null) return "Historique insuffisant";
  return `${(value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % / an`;
}

function formatMultipleChange(value: number | null | undefined): string {
  if (value == null) return "Historique insuffisant";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2, signDisplay: "always" })}× / an`;
}

function formatPointChange(value: number | null | undefined): string {
  if (value == null) return "Historique insuffisant";
  return `${(value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 2, signDisplay: "always" })} pt / an`;
}

function useReorderableKeys<Key extends string>(
  storageKey: string,
  defaultOrder: Key[],
) {
  const [order, setOrder] = useState<Key[]>(() => {
    try {
      const stored = JSON.parse(window.localStorage.getItem(storageKey) ?? "[]") as Key[];
      const valid = stored.filter((key) => defaultOrder.includes(key));
      return valid.length === defaultOrder.length && new Set(valid).size === defaultOrder.length
        ? valid
        : defaultOrder;
    } catch {
      return defaultOrder;
    }
  });

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(order));
  }, [order, storageKey]);

  const move = (key: Key, direction: -1 | 1) => {
    setOrder((current) => {
      const index = current.indexOf(key);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  return { order, move };
}

function MoveControls({
  label,
  index,
  total,
  onMove,
}: {
  label: string;
  index: number;
  total: number;
  onMove: (direction: -1 | 1) => void;
}) {
  return (
    <span className="move-controls">
      <button
        type="button"
        aria-label={`Déplacer ${label} vers la gauche`}
        title="Déplacer vers la gauche"
        disabled={index === 0}
        onClick={() => onMove(-1)}
      >
        <ArrowLeft aria-hidden="true" size={13} />
      </button>
      <button
        type="button"
        aria-label={`Déplacer ${label} vers la droite`}
        title="Déplacer vers la droite"
        disabled={index === total - 1}
        onClick={() => onMove(1)}
      >
        <ArrowRight aria-hidden="true" size={13} />
      </button>
    </span>
  );
}

function fundamentalValue(key: FundamentalKey, snapshot: FinancialAnalysis): string {
  const currency = snapshot.currency;
  switch (key) {
    case "revenue":
      return formatAmount(snapshot.revenue, currency);
    case "net_income":
      return formatAmount(snapshot.net_income, currency);
    case "pretax_income":
      return formatAmount(snapshot.pretax_income, currency);
    case "operating_income":
      return formatAmount(snapshot.ebit, currency);
    case "shares_outstanding":
      return formatShares(snapshot.shares_outstanding);
    case "market_cap":
      return formatAmount(snapshot.market_cap, currency);
    case "total_equity":
      return formatAmount(snapshot.total_equity, currency);
    case "operating_cash_flow":
      return formatAmount(snapshot.operating_cash_flow, currency);
    case "investing_cash_flow":
      return formatAmount(snapshot.investing_cash_flow, currency);
    case "closing_price":
      return formatPrice(snapshot.closing_price, currency);
    case "pe_ratio":
      return formatMultiple(ratio(snapshot.market_cap, snapshot.net_income));
    case "equity_value_per_share":
      return formatPrice(
        ratio(
          snapshot.total_equity + (snapshot.treasury_stock_value ?? 0),
          snapshot.shares_outstanding,
        ),
        currency,
      );
  }
}

function historyValue(key: HistoryColumnKey, snapshot: FinancialAnalysis): string {
  switch (key) {
    case "fiscal_year":
      return String(snapshot.fiscal_year);
    case "revenue":
      return formatAmount(snapshot.revenue, snapshot.currency);
    case "net_income":
      return formatAmount(snapshot.net_income, snapshot.currency);
    case "operating_income":
      return formatAmount(snapshot.ebit, snapshot.currency);
    case "pretax_income":
      return formatAmount(snapshot.pretax_income, snapshot.currency);
    case "closing_price":
      return formatPrice(snapshot.closing_price, snapshot.currency);
    case "pe_ratio":
      return formatMultiple(ratio(snapshot.market_cap, snapshot.net_income));
    case "roe":
      return formatRatio(ratio(snapshot.net_income, snapshot.total_equity));
    case "equity_to_assets":
      return formatRatio(ratio(snapshot.total_equity, snapshot.total_assets));
    case "operating_cash_flow":
      return formatAmount(snapshot.operating_cash_flow, snapshot.currency);
    case "mk_score":
      return snapshot.mk_score == null ? "N/A" : `${snapshot.mk_score}/100`;
  }
}

export function AnalysisDrawer({
  company,
  history,
  valuations,
  scores,
  loading,
  error,
  onCreateValuation,
  onCreateScore,
  onClose,
}: AnalysisDrawerProps) {
  const latest = history?.snapshots[0];
  const trend = history?.trend;
  const fundamentals = useReorderableKeys(
    "mkvip.analysis.fundamentals-order",
    FUNDAMENTAL_ORDER,
  );
  const trends = useReorderableKeys("mkvip.analysis.trends-order", TREND_ORDER);
  const historyColumns = useReorderableKeys(
    "mkvip.analysis.history-order",
    HISTORY_ORDER,
  );

  const trendValue = (key: TrendKey): string => {
    switch (key) {
      case "revenue":
        return formatGrowth(trend?.revenue_cagr);
      case "net_income":
        return formatGrowth(trend?.net_income_cagr);
      case "operating_income":
        return formatGrowth(trend?.operating_income_cagr);
      case "pretax_income":
        return formatGrowth(trend?.pretax_income_cagr);
      case "pe_ratio":
        return formatMultipleChange(trend?.pe_annual_change);
      case "roe":
        return formatPointChange(trend?.roe_annual_change);
      case "current_ratio":
        return formatMultipleChange(trend?.current_ratio_annual_change);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        onClick={onClose}
        aria-label="Fermer l’analyse financière"
      />
      <aside
        className="drawer drawer--wide analysis-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-title"
      >
        <div className="drawer__head">
          <div>
            <h2 id="analysis-title">Historique fondamental</h2>
            <p>{company.name} · {company.ticker}</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" />
          </button>
        </div>

        <div className="analysis-drawer__body">
          {loading && <p className="analysis-message">Chargement de l’analyse…</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          {!loading && !error && !latest && (
            <p className="analysis-message">Aucune analyse disponible.</p>
          )}
          {latest && history && (
            <>
              <div className="analysis-context">
                <span>{history.snapshots.length} exercice{history.snapshots.length > 1 ? "s" : ""} disponible{history.snapshots.length > 1 ? "s" : ""}</span>
                <span>{trend?.first_year}–{trend?.last_year}</span>
              </div>

              <section className="mk-score-summary" aria-label="Dernier MK Score">
                <div>
                  <span>MK Score</span>
                  <strong>{latest.mk_score == null ? "N/A" : `${latest.mk_score}/100`}</strong>
                </div>
                <p>
                  Dernier exercice disponible : {latest.fiscal_year}. L’affichage reste identique pour toutes les entreprises ; les données non applicables ou absentes sont signalées N/A.
                </p>
              </section>

              <section className="analysis-section" aria-labelledby="fundamentals-title">
                <div className="analysis-section__head">
                  <h3 id="fundamentals-title">Fondamentaux du dernier exercice</h3>
                  <span>{latest.fiscal_year} · montants en millions</span>
                </div>
                <div className="indicator-grid indicator-grid--fundamentals">
                  {fundamentals.order.map((key, index) => (
                    <article className="indicator-card indicator-card--movable" key={key}>
                      <div className="indicator-card__head">
                        <span>{FUNDAMENTAL_LABELS[key]}</span>
                        <MoveControls
                          label={FUNDAMENTAL_LABELS[key]}
                          index={index}
                          total={fundamentals.order.length}
                          onMove={(direction) => fundamentals.move(key, direction)}
                        />
                      </div>
                      <strong>{fundamentalValue(key, latest)}</strong>
                    </article>
                  ))}
                </div>
              </section>

              <section className="analysis-section" aria-labelledby="growth-title">
                <div className="analysis-section__head">
                  <h3 id="growth-title">Tendance annualisée</h3>
                  {trend && trend.periods >= 2 && <span>{trend.first_year}–{trend.last_year}</span>}
                </div>
                <div className="growth-grid growth-grid--reorderable">
                  {trends.order.map((key, index) => (
                    <article key={key}>
                      <div className="indicator-card__head">
                        <span>{TREND_LABELS[key]}</span>
                        <MoveControls
                          label={TREND_LABELS[key]}
                          index={index}
                          total={trends.order.length}
                          onMove={(direction) => trends.move(key, direction)}
                        />
                      </div>
                      <strong>{trendValue(key)}</strong>
                    </article>
                  ))}
                </div>
              </section>

              <section className="analysis-section" aria-labelledby="history-title">
                <div className="analysis-section__head">
                  <h3 id="history-title">Historique annuel</h3>
                  <span>Jusqu’aux 10 derniers exercices disponibles</span>
                </div>
                <div className="fundamental-history" role="table" aria-label="Historique fondamental">
                  <div
                    className="fundamental-history__head"
                    role="row"
                    style={{
                      gridTemplateColumns: `repeat(${historyColumns.order.length}, minmax(145px, 1fr))`,
                      minWidth: `${historyColumns.order.length * 145}px`,
                    }}
                  >
                    {historyColumns.order.map((key, index) => (
                      <span className="history-column-head" role="columnheader" key={key}>
                        {HISTORY_LABELS[key]}
                        <MoveControls
                          label={HISTORY_LABELS[key]}
                          index={index}
                          total={historyColumns.order.length}
                          onMove={(direction) => historyColumns.move(key, direction)}
                        />
                      </span>
                    ))}
                  </div>
                  {history.snapshots.slice(0, 10).map((snapshot) => (
                    <div
                      className="fundamental-history__row"
                      role="row"
                      key={snapshot.id}
                      style={{
                        gridTemplateColumns: `repeat(${historyColumns.order.length}, minmax(145px, 1fr))`,
                        minWidth: `${historyColumns.order.length * 145}px`,
                      }}
                    >
                      {historyColumns.order.map((key) => (
                        <span role="cell" key={key}>{historyValue(key, snapshot)}</span>
                      ))}
                    </div>
                  ))}
                </div>
              </section>

              <details className="analysis-details">
                <summary>Valorisation et score global</summary>
                {latest.analysis_profile === "financial" ? (
                  <p className="analysis-message">
                    Non applicable avec le modèle de valorisation industrielle actuel.
                  </p>
                ) : (
                  <>
                  <ValuationPanel snapshot={latest} valuations={valuations} onCreate={onCreateValuation} />
                  <ScorePanel fiscalYear={latest.fiscal_year} valuations={valuations} scores={scores} onCreate={onCreateScore} />
                  </>
                )}
              </details>

              <p className="analysis-disclaimer">
                Indicateurs de présélection explicables, sans recommandation d’investissement. Vérifier les chiffres dans les publications réglementaires.
              </p>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

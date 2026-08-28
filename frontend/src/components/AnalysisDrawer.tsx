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
import { PriceHistoryChart } from "./PriceHistoryChart";

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
  | "ebitda"
  | "operating_income"
  | "total_assets"
  | "market_cap"
  | "total_equity"
  | "operating_cash_flow"
  | "investing_cash_flow"
  | "closing_price"
  | "current_assets"
  | "equity_value_per_share";

type ComparisonKey =
  | "revenue"
  | "pe_ratio"
  | "current_ratio"
  | "market_cap_to_assets"
  | "gross_margin"
  | "net_margin"
  | "interest_burden"
  | "discount"
  | "stock_bond_yield"
  | "leverage"
  | "debt_level";

type HistoryColumnKey =
  | "fiscal_year"
  | "revenue"
  | "net_income"
  | "operating_income"
  | "ebitda"
  | "closing_price"
  | "pe_ratio"
  | "roe"
  | "equity_to_assets"
  | "operating_cash_flow"
  | "interest_burden"
  | "discount"
  | "stock_bond_yield"
  | "leverage"
  | "debt_level"
  | "mk_score";

const FUNDAMENTAL_ORDER: FundamentalKey[] = [
  "revenue",
  "net_income",
  "ebitda",
  "operating_income",
  "total_assets",
  "market_cap",
  "total_equity",
  "operating_cash_flow",
  "investing_cash_flow",
  "closing_price",
  "current_assets",
  "equity_value_per_share",
];

const COMPARISON_ORDER: ComparisonKey[] = [
  "revenue",
  "pe_ratio",
  "current_ratio",
  "market_cap_to_assets",
  "gross_margin",
  "net_margin",
  "interest_burden",
  "discount",
  "stock_bond_yield",
  "leverage",
  "debt_level",
];

const HISTORY_ORDER: HistoryColumnKey[] = [
  "fiscal_year",
  "revenue",
  "net_income",
  "operating_income",
  "ebitda",
  "closing_price",
  "pe_ratio",
  "roe",
  "equity_to_assets",
  "operating_cash_flow",
  "interest_burden",
  "discount",
  "stock_bond_yield",
  "leverage",
  "debt_level",
  "mk_score",
];

const FUNDAMENTAL_LABELS: Record<FundamentalKey, string> = {
  revenue: "Revenus publiés",
  net_income: "Résultat net",
  ebitda: "EBITDA",
  operating_income: "Résultat d’exploitation",
  total_assets: "Total actif",
  market_cap: "Capitalisation boursière",
  total_equity: "Capitaux propres",
  operating_cash_flow: "Flux de trésorerie d’exploitation",
  investing_cash_flow: "Flux de trésorerie d’investissement",
  closing_price: "Dernier cours de bourse au 31 décembre",
  current_assets: "Actif circulant",
  equity_value_per_share: "Valeur économique des capitaux propres par action",
};

const COMPARISON_LABELS: Record<ComparisonKey, string> = {
  revenue: "Revenus",
  pe_ratio: "Cours / bénéfice (PER)",
  current_ratio: "Current ratio",
  market_cap_to_assets: "Capitalisation boursière / total actif",
  gross_margin: "Marge brute",
  net_margin: "Marge nette",
  interest_burden: "Poids de la dette financière",
  discount: "Décote",
  stock_bond_yield: "Rendement de l’action-obligation",
  leverage: "Effet de levier ajusté",
  debt_level: "Niveau d’endettement",
};

const COMPARISON_FORMULAS: Record<ComparisonKey, string> = {
  revenue: "Chiffre d’affaires publié",
  pe_ratio: "Capitalisation boursière / résultat net",
  current_ratio: "Actif circulant / passif exigible",
  market_cap_to_assets: "Capitalisation boursière / total actif",
  gross_margin: "EBITDA / chiffre d’affaires",
  net_margin: "Résultat net / chiffre d’affaires",
  interest_burden: "Charges d’intérêts / EBIT",
  discount: "Capitalisation boursière / actif circulant",
  stock_bond_yield: "Résultat avant impôt / capitalisation boursière totale",
  leverage: "Passif total / (capitaux propres + réserve d’actions propres)",
  debt_level: "Dette financière nette / EBITDA",
};

const HISTORY_LABELS: Record<HistoryColumnKey, string> = {
  fiscal_year: "Exercice",
  revenue: "Revenus",
  net_income: "Résultat net",
  operating_income: "Résultat d’exploitation",
  ebitda: "EBITDA",
  closing_price: "Cours de clôture",
  pe_ratio: "PER",
  roe: "ROE",
  equity_to_assets: "Fonds propres / actif",
  operating_cash_flow: "Cash-flow d’exploitation",
  interest_burden: "Poids dette financière",
  discount: "Décote",
  stock_bond_yield: "Rendement action-obligation",
  leverage: "Effet de levier ajusté",
  debt_level: "Niveau d’endettement",
  mk_score: "MK Score",
};

const THRESHOLDS: Partial<
  Record<ComparisonKey, { value: number; direction: "above" | "below" }>
> = {
  pe_ratio: { value: 20, direction: "below" },
  current_ratio: { value: 2, direction: "above" },
  market_cap_to_assets: { value: 1.5, direction: "below" },
  gross_margin: { value: 0.4, direction: "above" },
  net_margin: { value: 0.2, direction: "above" },
  interest_burden: { value: 0.15, direction: "below" },
  discount: { value: 1, direction: "below" },
  leverage: { value: 0.8, direction: "below" },
  debt_level: { value: 2.5, direction: "below" },
};

const SECTOR_LABELS: Record<string, string> = {
  "Communication Services": "services de communication",
  "Consumer Discretionary": "consommation discrétionnaire",
  "Consumer Staples": "biens de consommation courante",
  Energy: "énergie",
  Financials: "services financiers",
  "Health Care": "santé",
  Industrials: "industrie",
  "Information Technology": "technologies de l’information",
  Materials: "matériaux",
  "Real Estate": "immobilier",
  Utilities: "services aux collectivités",
};

function compactBusinessSummary(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= 900) return normalized;
  const excerpt = normalized.slice(0, 900);
  const sentenceEnd = Math.max(
    excerpt.lastIndexOf(". "),
    excerpt.lastIndexOf("! "),
    excerpt.lastIndexOf("? "),
  );
  if (sentenceEnd >= 450) return excerpt.slice(0, sentenceEnd + 1);
  const wordEnd = excerpt.lastIndexOf(" ");
  return `${excerpt.slice(0, wordEnd)}…`;
}

function activitySummary(company: Company): { text: string; source: string } {
  if (company.business_summary?.trim()) {
    return {
      text: compactBusinessSummary(company.business_summary),
      source: "Profil public de l’entreprise",
    };
  }
  const sector = company.sector
    ? SECTOR_LABELS[company.sector] ?? company.sector
    : null;
  if (company.industry || sector) {
    const activity = company.industry
      ? `dans l’activité « ${company.industry} »`
      : `dans le secteur ${sector}`;
    const sectorDetail = company.industry && sector ? `, rattachée au secteur ${sector}` : "";
    return {
      text: `${company.name} exerce principalement ${activity}${sectorDetail}. L’entreprise est établie en ${company.country} et ses titres sont négociés sur ${company.exchange}.`,
      source: "Résumé basé sur la classification disponible",
    };
  }
  return {
    text: `Le résumé détaillé de ${company.name} n’est pas encore disponible. Rechargez l’historique financier pour actualiser son profil public.`,
    source: "Profil à actualiser",
  };
}

function formatAmount(value: number | null | undefined, currency: string): string {
  if (value == null) return "N/A";
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M ${currency}`;
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

function comparisonValue(key: ComparisonKey, snapshot: FinancialAnalysis): number | null {
  switch (key) {
    case "revenue":
      return snapshot.revenue;
    case "pe_ratio":
      return ratio(snapshot.market_cap, snapshot.net_income);
    case "current_ratio":
      return ratio(snapshot.current_assets, snapshot.current_liabilities);
    case "market_cap_to_assets":
      return ratio(snapshot.market_cap, snapshot.total_assets);
    case "gross_margin":
      return ratio(snapshot.ebitda, snapshot.revenue);
    case "net_margin":
      return ratio(snapshot.net_income, snapshot.revenue);
    case "interest_burden":
      return ratio(snapshot.interest_expense, snapshot.ebit);
    case "discount":
      return ratio(snapshot.market_cap, snapshot.current_assets);
    case "stock_bond_yield":
      return ratio(snapshot.pretax_income, snapshot.market_cap);
    case "leverage": {
      const totalLiabilities = snapshot.total_assets - snapshot.total_equity;
      if (totalLiabilities < 0) return null;
      return ratio(
        totalLiabilities,
        snapshot.total_equity + (snapshot.treasury_stock_value ?? 0),
      );
    }
    case "debt_level":
      if (snapshot.financial_debt == null || snapshot.cash == null) return null;
      return ratio(snapshot.financial_debt - snapshot.cash, snapshot.ebitda);
  }
}

function formatComparisonValue(
  key: ComparisonKey,
  value: number | null,
  currency: string,
): string {
  if (key === "revenue") return formatAmount(value, currency);
  if (
    key === "pe_ratio"
    || key === "current_ratio"
    || key === "market_cap_to_assets"
    || key === "leverage"
    || key === "debt_level"
  ) {
    return formatMultiple(value);
  }
  return formatRatio(value);
}

function formatComparisonDelta(
  key: ComparisonKey,
  current: number | null,
  previous: number | null,
): string {
  if (current == null || previous == null) return "Comparaison indisponible";
  if (key === "revenue") {
    if (previous <= 0) return "Comparaison indisponible";
    return `${((current - previous) / previous * 100).toLocaleString("fr-FR", {
      maximumFractionDigits: 1,
      signDisplay: "always",
    })} %`;
  }
  if (
    key === "pe_ratio"
    || key === "current_ratio"
    || key === "market_cap_to_assets"
    || key === "leverage"
    || key === "debt_level"
  ) {
    return `${(current - previous).toLocaleString("fr-FR", {
      maximumFractionDigits: 2,
      signDisplay: "always",
    })}×`;
  }
  return `${((current - previous) * 100).toLocaleString("fr-FR", {
    maximumFractionDigits: 1,
    signDisplay: "always",
  })} pt`;
}

function comparisonTone(key: ComparisonKey, value: number | null): string {
  const rule = THRESHOLDS[key];
  if (rule == null || value == null) return "comparison-value--neutral";
  const isFavorable = rule.direction === "above"
    ? value > rule.value
    : value < rule.value;
  return isFavorable
    ? "comparison-value--favorable"
    : "comparison-value--unfavorable";
}

function thresholdLabel(key: ComparisonKey): string | null {
  const rule = THRESHOLDS[key];
  if (rule == null) return null;
  const formatted = key === "pe_ratio"
    || key === "current_ratio"
    || key === "market_cap_to_assets"
    || key === "leverage"
    || key === "debt_level"
    ? `${rule.value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}×`
    : `${(rule.value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
  return `Seuil vert : ${rule.direction === "above" ? ">" : "<"} ${formatted}`;
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
    case "ebitda":
      return formatAmount(snapshot.ebitda, currency);
    case "operating_income":
      return formatAmount(snapshot.ebit, currency);
    case "total_assets":
      return formatAmount(snapshot.total_assets, currency);
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
    case "current_assets":
      return formatAmount(snapshot.current_assets, currency);
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
    case "ebitda":
      return formatAmount(snapshot.ebitda, snapshot.currency);
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
    case "interest_burden":
    case "discount":
    case "stock_bond_yield":
      return formatRatio(comparisonValue(key, snapshot));
    case "leverage":
    case "debt_level":
      return formatMultiple(comparisonValue(key, snapshot));
    case "mk_score":
      return snapshot.mk_score == null ? "N/A" : `${snapshot.mk_score}/100`;
  }
}

function historyValueClass(
  key: HistoryColumnKey,
  snapshot: FinancialAnalysis,
): string | undefined {
  if (
    !COMPARISON_ORDER.includes(key as ComparisonKey)
    || key === "revenue"
    || key === "pe_ratio"
  ) {
    return undefined;
  }
  return comparisonTone(key as ComparisonKey, comparisonValue(key as ComparisonKey, snapshot));
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
  const previous = history?.snapshots[1];
  const trend = history?.trend;
  const fundamentals = useReorderableKeys(
    "mkvip.analysis.fundamentals-order",
    FUNDAMENTAL_ORDER,
  );
  const comparisons = useReorderableKeys(
    "mkvip.analysis.comparisons-order",
    COMPARISON_ORDER,
  );
  const historyColumns = useReorderableKeys(
    "mkvip.analysis.history-order",
    HISTORY_ORDER,
  );
  const activity = activitySummary(company);

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
          {!loading && !error && !latest && history && (
            <>
              <p className="analysis-message analysis-message--partial">
                Les cours et le profil public sont disponibles. Les comptes annuels
                structurés ne sont pas fournis par les sources gratuites connectées ;
                aucun ratio ni MK Score n’est donc calculé avec des données incomplètes.
              </p>
              <section
                className="analysis-section business-summary"
                aria-labelledby="business-summary-title"
              >
                <div className="analysis-section__head">
                  <h3 id="business-summary-title">Résumé de l’activité</h3>
                  <span>{activity.source}</span>
                </div>
                <p>{activity.text}</p>
                <div className="business-summary__facts" aria-label="Informations sur l’activité">
                  {company.sector && <span>{SECTOR_LABELS[company.sector] ?? company.sector}</span>}
                  {company.industry && <span>{company.industry}</span>}
                  <span>{company.country}</span>
                </div>
              </section>
              <PriceHistoryChart history={history.price_history} />
            </>
          )}
          {latest && history && (
            <>
              <div className="analysis-context">
                <span>{history.snapshots.length} exercice{history.snapshots.length > 1 ? "s" : ""} disponible{history.snapshots.length > 1 ? "s" : ""}</span>
                <span>{trend?.first_year}–{trend?.last_year}</span>
              </div>

              <section
                className="analysis-section business-summary"
                aria-labelledby="business-summary-title"
              >
                <div className="analysis-section__head">
                  <h3 id="business-summary-title">Résumé de l’activité</h3>
                  <span>{activity.source}</span>
                </div>
                <p>{activity.text}</p>
                <div className="business-summary__facts" aria-label="Informations sur l’activité">
                  {company.sector && <span>{SECTOR_LABELS[company.sector] ?? company.sector}</span>}
                  {company.industry && <span>{company.industry}</span>}
                  <span>{company.country}</span>
                </div>
              </section>

              <PriceHistoryChart history={history.price_history} />

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
                  <h3 id="growth-title">Comparaison des deux derniers exercices</h3>
                  <span>
                    {previous
                      ? `${latest.fiscal_year} vs ${previous.fiscal_year}`
                      : `Dernier exercice : ${latest.fiscal_year}`}
                  </span>
                </div>
                <div className="growth-grid comparison-grid growth-grid--reorderable">
                  {comparisons.order.map((key, index) => {
                    const currentValue = comparisonValue(key, latest);
                    const previousValue = previous ? comparisonValue(key, previous) : null;
                    const threshold = thresholdLabel(key);
                    return (
                    <article key={key} title={COMPARISON_FORMULAS[key]}>
                      <div className="indicator-card__head">
                        <span>{COMPARISON_LABELS[key]}</span>
                        <MoveControls
                          label={COMPARISON_LABELS[key]}
                          index={index}
                          total={comparisons.order.length}
                          onMove={(direction) => comparisons.move(key, direction)}
                        />
                      </div>
                      <strong className={comparisonTone(key, currentValue)}>
                        {formatComparisonValue(key, currentValue, latest.currency)}
                      </strong>
                      {previous ? (
                        <small className="comparison-card__previous">
                          {previous.fiscal_year} : {formatComparisonValue(
                            key,
                            previousValue,
                            previous.currency,
                          )}
                          <span>Évolution : {formatComparisonDelta(key, currentValue, previousValue)}</span>
                        </small>
                      ) : (
                        <small className="comparison-card__previous">Historique insuffisant</small>
                      )}
                      {threshold && <small className="comparison-card__threshold">{threshold}</small>}
                    </article>
                    );
                  })}
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
                      <span
                        className="history-column-head"
                        role="columnheader"
                        key={key}
                        title={COMPARISON_ORDER.includes(key as ComparisonKey)
                          ? COMPARISON_FORMULAS[key as ComparisonKey]
                          : undefined}
                      >
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
                        <span
                          className={historyValueClass(key, snapshot)}
                          role="cell"
                          key={key}
                        >
                          {historyValue(key, snapshot)}
                        </span>
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

import { useMemo, useState } from "react";

import type { PriceHistory, PricePoint } from "../api/client";

type PriceRange = "1y" | "3y" | "5y" | "10y" | "max";

const RANGES: Array<{ key: PriceRange; label: string; years: number | null }> = [
  { key: "1y", label: "1 an", years: 1 },
  { key: "3y", label: "3 ans", years: 3 },
  { key: "5y", label: "5 ans", years: 5 },
  { key: "10y", label: "10 ans", years: 10 },
  { key: "max", label: "Max", years: null },
];

function priceValue(point: PricePoint): number {
  return point.adjusted_close ?? point.close;
}

function formatPrice(value: number, currency: string): string {
  return value.toLocaleString("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: value < 10 ? 3 : 2,
  });
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function pointsForRange(points: PricePoint[], range: PriceRange): PricePoint[] {
  const years = RANGES.find((item) => item.key === range)?.years;
  if (years == null || points.length === 0) return points;
  const lastDate = new Date(`${points[points.length - 1].date}T12:00:00`);
  const cutoff = new Date(lastDate);
  cutoff.setFullYear(cutoff.getFullYear() - years);
  return points.filter((point) => new Date(`${point.date}T12:00:00`) >= cutoff);
}

export function PriceHistoryChart({ history }: { history: PriceHistory | null | undefined }) {
  const [range, setRange] = useState<PriceRange>("5y");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const points = useMemo(
    () => pointsForRange(history?.points ?? [], range),
    [history, range],
  );

  if (!history || points.length < 2) {
    return (
      <section className="analysis-section price-history" aria-labelledby="price-history-title">
        <div className="analysis-section__head">
          <h3 id="price-history-title">Historique du cours de bourse</h3>
        </div>
        <p className="analysis-message">Historique indisponible pour cette valeur.</p>
      </section>
    );
  }

  const width = 820;
  const height = 280;
  const padding = { top: 24, right: 28, bottom: 36, left: 74 };
  const values = points.map(priceValue);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const spread = maximum - minimum || Math.max(maximum * 0.05, 1);
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const xAt = (index: number) => padding.left + (index / (points.length - 1)) * chartWidth;
  const yAt = (value: number) => padding.top + ((maximum - value) / spread) * chartHeight;
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${xAt(index).toFixed(2)},${yAt(priceValue(point)).toFixed(2)}`)
    .join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const performance = (priceValue(last) / priceValue(first) - 1) * 100;
  const activeIndex = hoveredIndex ?? points.length - 1;
  const active = points[activeIndex];
  const activeX = xAt(activeIndex);
  const activeY = yAt(priceValue(active));

  return (
    <section className="analysis-section price-history" aria-labelledby="price-history-title">
      <div className="analysis-section__head price-history__head">
        <div>
          <h3 id="price-history-title">Historique du cours de bourse</h3>
          <span>Cours ajusté lorsque disponible · {history.source}</span>
        </div>
        <div className="price-history__ranges" aria-label="Période du graphique">
          {RANGES.map((item) => (
            <button
              type="button"
              key={item.key}
              className={range === item.key ? "is-active" : undefined}
              aria-pressed={range === item.key}
              onClick={() => {
                setRange(item.key);
                setHoveredIndex(null);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="price-history__summary">
        <strong>{formatPrice(priceValue(active), history.currency)}</strong>
        <span>{formatDate(active.date)}</span>
        <span className={performance >= 0 ? "is-positive" : "is-negative"}>
          {performance.toLocaleString("fr-FR", { maximumFractionDigits: 1, signDisplay: "always" })} % sur la période
        </span>
      </div>

      <div className="price-history__chart">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Cours de ${formatPrice(priceValue(first), history.currency)} à ${formatPrice(priceValue(last), history.currency)}`}
          onMouseLeave={() => setHoveredIndex(null)}
          onMouseMove={(event) => {
            const bounds = event.currentTarget.getBoundingClientRect();
            const relativeX = (event.clientX - bounds.left) / bounds.width * width;
            const index = Math.round((relativeX - padding.left) / chartWidth * (points.length - 1));
            setHoveredIndex(Math.max(0, Math.min(points.length - 1, index)));
          }}
        >
          {[0, 0.5, 1].map((ratio) => {
            const value = maximum - spread * ratio;
            const y = padding.top + chartHeight * ratio;
            return (
              <g key={ratio}>
                <line className="price-history__grid" x1={padding.left} x2={width - padding.right} y1={y} y2={y} />
                <text className="price-history__axis" x={padding.left - 10} y={y + 4} textAnchor="end">
                  {value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}
                </text>
              </g>
            );
          })}
          <path className="price-history__line" d={path} />
          <line className="price-history__cursor" x1={activeX} x2={activeX} y1={padding.top} y2={height - padding.bottom} />
          <circle className="price-history__dot" cx={activeX} cy={activeY} r="5" />
          <text className="price-history__axis" x={padding.left} y={height - 10}>{formatDate(first.date)}</text>
          <text className="price-history__axis" x={width - padding.right} y={height - 10} textAnchor="end">{formatDate(last.date)}</text>
        </svg>
      </div>
    </section>
  );
}

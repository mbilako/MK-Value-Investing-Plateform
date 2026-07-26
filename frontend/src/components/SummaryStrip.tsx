interface SummaryStripProps {
  companies: number;
  analyses: number;
}

export function SummaryStrip({
  companies,
  analyses,
}: SummaryStripProps) {
  const metrics = [
    { value: companies, label: "entreprises" },
    { value: analyses, label: "analyses" },
    { value: 0, label: "alertes" },
  ];

  return (
    <section className="summary-strip" aria-label="Résumé">
      {metrics.map((metric) => (
        <div
          className="summary-strip__item"
          key={metric.label}
          aria-label={`${metric.label} : ${metric.value}`}
        >
          <strong>{metric.value}</strong>
          <span>{metric.label}</span>
        </div>
      ))}
    </section>
  );
}

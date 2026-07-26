interface SummaryStripProps {
  companies: number;
  analyses: number;
  favorable: number;
}

export function SummaryStrip({
  companies,
  analyses,
  favorable,
}: SummaryStripProps) {
  const metrics = [
    { value: companies, label: "entreprises" },
    { value: analyses, label: "analyses" },
    { value: favorable, label: "profils favorables" },
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

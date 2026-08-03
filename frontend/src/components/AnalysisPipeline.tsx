import {
  Calculator,
  CheckCircle2,
  DatabaseZap,
  Download,
  Star,
} from "lucide-react";

const steps = [
  { label: "Import", icon: Download },
  { label: "Validation", icon: CheckCircle2 },
  { label: "Normalisation", icon: DatabaseZap },
  { label: "Ratios", icon: Calculator },
  { label: "MK Score", icon: Star },
];

export function AnalysisPipeline() {
  return (
    <section className="section" id="rules" aria-labelledby="pipeline-title">
      <h2 id="pipeline-title">Méthode MK</h2>
      <p className="section-intro">
        Dix règles simples sont évaluées pour chaque exercice disponible afin
        de rendre la tendance lisible et comparable.
      </p>
      <ol className="pipeline">
        {steps.map(({ label, icon: Icon }, index) => (
          <li key={label}>
            <span className="pipeline__icon">
              <Icon aria-hidden="true" size={24} strokeWidth={1.7} />
            </span>
            <strong>{label}</strong>
            {index < steps.length - 1 && (
              <span className="pipeline__line" aria-hidden="true" />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

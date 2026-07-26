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
    <section className="section" aria-labelledby="pipeline-title">
      <h2 id="pipeline-title">Moteur d’analyse</h2>
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

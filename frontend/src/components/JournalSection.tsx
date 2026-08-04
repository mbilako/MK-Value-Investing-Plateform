import { ArrowUpRight, BookOpen } from "lucide-react";

import type { Company, Dashboard } from "../api/client";

interface JournalSectionProps {
  dashboard: Dashboard | null;
  companies: Company[];
  onAnalysis: (company: Company) => void;
}

export function JournalSection({
  dashboard,
  companies,
  onAnalysis,
}: JournalSectionProps) {
  const companyById = new Map(companies.map((company) => [company.id, company]));
  const entries = [...(dashboard?.companies ?? [])]
    .filter((entry) => entry.updated_at)
    .sort((left, right) =>
      (right.updated_at ?? "").localeCompare(left.updated_at ?? ""),
    )
    .slice(0, 10);

  return (
    <section
      className="section journal-section"
      id="journal"
      aria-labelledby="journal-title"
    >
      <div className="decision-subhead">
        <BookOpen aria-hidden="true" size={20} />
        <h2 id="journal-title">Journal des analyses</h2>
      </div>
      {entries.length ? (
        <div className="journal-list">
          {entries.map((entry) => {
            const company = companyById.get(entry.company_id);
            return (
              <article key={entry.company_id} className="journal-entry">
                <div>
                  <strong>{entry.name}</strong>
                  <span>
                    Exercice {entry.fiscal_year ?? "—"} · {entry.signal_label}
                  </span>
                </div>
                <time dateTime={entry.updated_at ?? undefined}>
                  {entry.updated_at
                    ? new Date(entry.updated_at).toLocaleDateString("fr-FR")
                    : ""}
                </time>
                {company?.status === "ready" && (
                  <button
                    className="portfolio-open"
                    onClick={() => onAnalysis(company)}
                    aria-label={`Ouvrir l’analyse de ${entry.name}`}
                  >
                    <ArrowUpRight aria-hidden="true" size={17} />
                  </button>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="analysis-message">
          Les analyses chargées apparaîtront ici, de la plus récente à la plus
          ancienne.
        </p>
      )}
    </section>
  );
}

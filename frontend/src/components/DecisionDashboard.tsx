import { useMemo, useState } from "react";
import { ArrowUpRight, BarChart3, Settings2 } from "lucide-react";

import type {
  Company,
  Dashboard,
  DashboardSignal,
} from "../api/client";

interface DecisionDashboardProps {
  dashboard: Dashboard;
  companies: Company[];
  onAnalysis: (company: Company) => void;
  onManage: (company: Company) => void;
}

type DashboardFilter = "all" | DashboardSignal;

const signalExplanations: Record<DashboardSignal, string> = {
  favorable: "Profil favorable",
  watch: "À approfondir",
  caution: "Prudence",
  unscored: "À scorer",
};

function formatMarketGap(value: number | null) {
  if (value == null) return "Non disponible";
  return new Intl.NumberFormat("fr-FR", {
    style: "percent",
    maximumFractionDigits: 1,
    signDisplay: "always",
  }).format(value);
}

export function DecisionDashboard({
  dashboard,
  companies,
  onAnalysis,
  onManage,
}: DecisionDashboardProps) {
  const [filter, setFilter] = useState<DashboardFilter>("all");
  const companyById = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies],
  );
  const visibleCompanies = useMemo(
    () =>
      filter === "all"
        ? dashboard.companies
        : dashboard.companies.filter((company) => company.signal === filter),
    [dashboard.companies, filter],
  );
  const distributionTotal = Math.max(dashboard.summary.companies, 1);

  return (
    <section className="section decision-dashboard" aria-labelledby="decision-title">
      <div className="decision-dashboard__head">
        <div>
          <p className="section-eyebrow">Lecture comparative</p>
          <h2 id="decision-title">Tableau de décision</h2>
        </div>
        <p>
          Priorisez les dossiers à étudier grâce au dernier scoring disponible.
        </p>
      </div>

      <div className="decision-layout">
        <section
          className="signal-distribution"
          aria-labelledby="distribution-title"
        >
          <div className="decision-subhead">
            <BarChart3 aria-hidden="true" size={19} />
            <h3 id="distribution-title">Distribution des signaux</h3>
          </div>
          <div
            className="signal-distribution__bar"
            aria-label={`${dashboard.summary.scored} entreprises scorées sur ${dashboard.summary.companies}`}
          >
            {dashboard.distribution.map((item) => (
              <span
                key={item.signal}
                data-signal={item.signal}
                style={{ width: `${(item.count / distributionTotal) * 100}%` }}
              />
            ))}
          </div>
          <dl className="signal-distribution__legend">
            {dashboard.distribution.map((item) => (
              <div key={item.signal}>
                <dt>
                  <span data-signal={item.signal} aria-hidden="true" />
                  {item.label}
                </dt>
                <dd>{item.count}</dd>
              </div>
            ))}
          </dl>
          <p className="signal-distribution__note">
            {dashboard.summary.scored} dossier
            {dashboard.summary.scored > 1 ? "s" : ""} scoré
            {dashboard.summary.scored > 1 ? "s" : ""} ·{" "}
            {dashboard.summary.unscored} à compléter
          </p>
        </section>

        <section
          className="research-portfolio"
          aria-labelledby="portfolio-title"
        >
          <div className="research-portfolio__head">
            <div>
              <h3 id="portfolio-title">Portefeuille de recherche</h3>
              <p>Univers d’étude, sans position ni recommandation implicite.</p>
            </div>
            <label className="portfolio-filter">
              <span className="sr-only">
                Filtrer le portefeuille de recherche
              </span>
              <select
                value={filter}
                onChange={(event) =>
                  setFilter(event.target.value as DashboardFilter)
                }
                aria-label="Filtrer le portefeuille de recherche"
              >
                <option value="all">Tous les signaux</option>
                <option value="favorable">Profils favorables</option>
                <option value="watch">À approfondir</option>
                <option value="caution">Prudence</option>
                <option value="unscored">À scorer</option>
              </select>
            </label>
          </div>

          <div className="portfolio-table">
            <div className="portfolio-table__head" role="row">
              <span>Entreprise</span>
              <span>MK Global</span>
              <span>Signal</span>
              <span>Écart valeur</span>
              <span>Point à approfondir</span>
              <span aria-hidden="true" />
            </div>
            <div className="portfolio-table__body">
              {visibleCompanies.map((row) => {
                const company = companyById.get(row.company_id);
                return (
                  <div
                    className="portfolio-table__row"
                    role="row"
                    key={row.company_id}
                  >
                    <div className="portfolio-company">
                      <strong>{row.name}</strong>
                      <span>
                        {row.ticker} · {row.exchange}
                      </span>
                    </div>
                    <strong className="portfolio-score">
                      {row.global_score ?? "—"}
                    </strong>
                    <span className="portfolio-signal" data-signal={row.signal}>
                      {row.signal_label || signalExplanations[row.signal]}
                    </span>
                    <span className="portfolio-gap">
                      {formatMarketGap(row.market_gap)}
                    </span>
                    <span className="portfolio-weakness">
                      {row.weakest_component ? (
                        <>
                          <strong>{row.weakest_component.label}</strong>
                          <small>{row.weakest_component.score}/100</small>
                        </>
                      ) : (
                        "Scoring requis"
                      )}
                    </span>
                    <div className="portfolio-row-actions">
                      {company?.status === "ready" && (
                        <button
                          className="portfolio-open"
                          onClick={() => onAnalysis(company)}
                          aria-label={`Ouvrir l’analyse de ${row.name}`}
                        >
                          <ArrowUpRight aria-hidden="true" size={17} />
                        </button>
                      )}
                      {company && (
                        <button
                          className="portfolio-open"
                          onClick={() => onManage(company)}
                          aria-label={`Modifier ou retirer ${row.name}`}
                          title="Modifier ou retirer"
                        >
                          <Settings2 aria-hidden="true" size={17} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
              {!visibleCompanies.length && (
                <p className="portfolio-table__empty">
                  Aucun dossier ne correspond à ce filtre.
                </p>
              )}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

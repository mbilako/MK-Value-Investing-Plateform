import { useMemo, useState, type FormEvent } from "react";
import {
  BookOpenCheck,
  FileSearch,
  LoaderCircle,
  MessageSquareText,
  Scale,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";

import type {
  AIAnalysis,
  AIAnalysisMode,
  AIAnalysisPayload,
  Company,
} from "../api/client";

interface AIAnalystDrawerProps {
  companies: Company[];
  onAnalyze: (payload: AIAnalysisPayload) => Promise<AIAnalysis>;
  onClose: () => void;
}

const modes: Array<{
  id: AIAnalysisMode;
  label: string;
  description: string;
}> = [
  {
    id: "summary",
    label: "Synthèse",
    description: "Résumer le dossier à partir des analyses MK-VIP.",
  },
  {
    id: "comparison",
    label: "Comparaison",
    description: "Comparer deux dossiers sans classement automatique.",
  },
  {
    id: "question",
    label: "Question",
    description: "Poser une question ciblée sur les données disponibles.",
  },
];

const sourceKindLabels = {
  financial: "Analyse financière",
  valuation: "Valorisation",
  scoring: "Scoring",
};

export function AIAnalystDrawer({
  companies,
  onAnalyze,
  onClose,
}: AIAnalystDrawerProps) {
  const [mode, setMode] = useState<AIAnalysisMode>("summary");
  const [companyId, setCompanyId] = useState(companies[0]?.id ?? "");
  const [comparisonCompanyId, setComparisonCompanyId] = useState(
    companies.find((company) => company.id !== companies[0]?.id)?.id ?? "",
  );
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AIAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const primaryCompany = useMemo(
    () => companies.find((company) => company.id === companyId),
    [companies, companyId],
  );
  const comparisonCompanies = companies.filter(
    (company) => company.id !== companyId,
  );

  const selectMode = (nextMode: AIAnalysisMode) => {
    setMode(nextMode);
    setResult(null);
    setError(null);
    if (
      nextMode === "comparison" &&
      (!comparisonCompanyId || comparisonCompanyId === companyId)
    ) {
      setComparisonCompanyId(comparisonCompanies[0]?.id ?? "");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const payload: AIAnalysisPayload = { mode, company_id: companyId };
    if (mode === "comparison") {
      payload.comparison_company_id = comparisonCompanyId;
    }
    if (mode === "question") {
      payload.question = question.trim();
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await onAnalyze(payload));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "L’analyse IA n’a pas pu être générée.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop drawer-backdrop--ai"
        onClick={onClose}
        aria-label="Fermer l’Analyste IA"
      />
      <aside
        className="drawer drawer--wide ai-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-analyst-title"
      >
        <div className="drawer__head ai-drawer__head">
          <div>
            <p className="ai-drawer__eyebrow">
              <Sparkles aria-hidden="true" size={15} />
              Assistance à la recherche
            </p>
            <h2 id="ai-analyst-title">Analyste IA</h2>
            <p>
              {primaryCompany
                ? `${primaryCompany.name} · ${primaryCompany.ticker}`
                : "Sélectionnez un dossier analysé"}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <X aria-hidden="true" />
          </button>
        </div>

        <form className="ai-drawer__form" onSubmit={submit}>
          <div className="ai-drawer__body">
            <section className="ai-compose" aria-labelledby="ai-mode-title">
              <div>
                <p className="section-eyebrow" id="ai-mode-title">
                  Type d’analyse
                </p>
                <div className="ai-mode-switch" aria-label="Type d’analyse">
                  {modes.map((item) => (
                    <button
                      key={item.id}
                      className="ai-mode-switch__button"
                      data-active={mode === item.id || undefined}
                      type="button"
                      onClick={() => selectMode(item.id)}
                    >
                      {item.id === "summary" && (
                        <FileSearch aria-hidden="true" size={17} />
                      )}
                      {item.id === "comparison" && (
                        <Scale aria-hidden="true" size={17} />
                      )}
                      {item.id === "question" && (
                        <MessageSquareText aria-hidden="true" size={17} />
                      )}
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="ai-mode-description">
                  {modes.find((item) => item.id === mode)?.description}
                </p>
              </div>

              <div className="ai-context-grid">
                <label className="field">
                  <span>Entreprise analysée</span>
                  <select
                    value={companyId}
                    onChange={(event) => {
                      const nextCompanyId = event.target.value;
                      setCompanyId(nextCompanyId);
                      if (comparisonCompanyId === nextCompanyId) {
                        setComparisonCompanyId(
                          companies.find(
                            (company) => company.id !== nextCompanyId,
                          )?.id ?? "",
                        );
                      }
                      setResult(null);
                    }}
                    required
                  >
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name} · {company.ticker}
                      </option>
                    ))}
                  </select>
                </label>

                {mode === "comparison" && (
                  <label className="field">
                    <span>Entreprise de comparaison</span>
                    <select
                      value={comparisonCompanyId}
                      onChange={(event) => {
                        setComparisonCompanyId(event.target.value);
                        setResult(null);
                      }}
                      required
                    >
                      {comparisonCompanies.map((company) => (
                        <option key={company.id} value={company.id}>
                          {company.name} · {company.ticker}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              {mode === "question" && (
                <label className="field">
                  <span>Question à analyser</span>
                  <textarea
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ex. Quels sont les principaux points de vigilance ?"
                    minLength={3}
                    maxLength={800}
                    required
                  />
                </label>
              )}

              <div className="ai-compose__action">
                <button
                  className="button button--primary"
                  type="submit"
                  disabled={
                    loading ||
                    !companyId ||
                    (mode === "comparison" && !comparisonCompanyId) ||
                    (mode === "question" && question.trim().length < 3)
                  }
                >
                  {loading ? (
                    <LoaderCircle
                      className="ai-loading"
                      aria-hidden="true"
                      size={18}
                    />
                  ) : (
                    <Sparkles aria-hidden="true" size={18} />
                  )}
                  {loading ? "Analyse en cours…" : "Analyser avec l’IA"}
                </button>
                <p>
                  Contexte fermé : seules les analyses MK-VIP disponibles sont
                  transmises.
                </p>
              </div>
            </section>

            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}

            {result && (
              <article className="ai-result" aria-live="polite">
                <header className="ai-result__lead">
                  <span>Conclusion</span>
                  <h3>{result.headline}</h3>
                  <p>{result.conclusion}</p>
                </header>

                <section className="ai-result__section">
                  <div className="ai-result__title">
                    <BookOpenCheck aria-hidden="true" size={19} />
                    <h4>Ce que montrent les données</h4>
                  </div>
                  <div className="ai-evidence">
                    {result.evidence.map((item) => (
                      <article key={`${item.title}-${item.finding}`}>
                        <h5>{item.title}</h5>
                        <p>{item.finding}</p>
                        <div className="ai-source-tags">
                          {item.source_ids.map((sourceId) => (
                            <span key={sourceId}>
                              Source{" "}
                              {result.sources.findIndex(
                                (source) => source.id === sourceId,
                              ) + 1}
                            </span>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </section>

                <div className="ai-result__columns">
                  <section className="ai-result__section">
                    <div className="ai-result__title">
                      <ShieldAlert aria-hidden="true" size={19} />
                      <h4>Points de vigilance</h4>
                    </div>
                    <ul>
                      {result.risks.map((risk) => (
                        <li key={risk}>{risk}</li>
                      ))}
                    </ul>
                  </section>
                  <section className="ai-result__section">
                    <div className="ai-result__title">
                      <FileSearch aria-hidden="true" size={19} />
                      <h4>À vérifier</h4>
                    </div>
                    <ul>
                      {result.missing_information.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </section>
                </div>

                <section className="ai-result__sources">
                  <h4>Sources MK-VIP utilisées</h4>
                  <ol>
                    {result.sources.map((source) => (
                      <li key={source.id}>
                        <span>{source.label}</span>
                        <small>{sourceKindLabels[source.kind]}</small>
                      </li>
                    ))}
                  </ol>
                </section>

                <p className="analysis-disclaimer">
                  {result.disclaimer}
                </p>
              </article>
            )}
          </div>
        </form>
      </aside>
    </div>
  );
}

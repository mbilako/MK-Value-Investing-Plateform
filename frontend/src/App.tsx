import { useEffect, useState } from "react";
import { Plus, Sparkles } from "lucide-react";

import {
  apiClient,
  type Company,
  type CompanyClient,
  type Dashboard,
  type AIAnalysisPayload,
  type FinancialAnalysis,
  type FinancialHistory,
  type ScoringAnalysis,
  type ScoringPayload,
  type ValuationAnalysis,
  type ValuationPayload,
} from "./api/client";
import { AnalysisDrawer } from "./components/AnalysisDrawer";
import { AIAnalystDrawer } from "./components/AIAnalystDrawer";
import { AnalysisPipeline } from "./components/AnalysisPipeline";
import { CompanyUniverse } from "./components/CompanyUniverse";
import { DecisionDashboard } from "./components/DecisionDashboard";
import { FinancialDrawer } from "./components/FinancialDrawer";
import { ImportDrawer } from "./components/ImportDrawer";
import { Sidebar } from "./components/Sidebar";
import { SummaryStrip } from "./components/SummaryStrip";

interface AppProps {
  client?: CompanyClient;
}

export function App({ client = apiClient }: AppProps) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [isImportOpen, setImportOpen] = useState(false);
  const [isAIAnalystOpen, setAIAnalystOpen] = useState(false);
  const [financialCompany, setFinancialCompany] = useState<Company | null>(
    null,
  );
  const [scores, setScores] = useState<Record<string, number>>({});
  const [analysisCompany, setAnalysisCompany] = useState<Company | null>(null);
  const [financialHistory, setFinancialHistory] =
    useState<FinancialHistory | null>(null);
  const [valuations, setValuations] = useState<ValuationAnalysis[]>([]);
  const [scoringAnalyses, setScoringAnalyses] = useState<ScoringAnalysis[]>([]);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const aiCompanies = companies.filter(
    (company) => company.status === "ready",
  );

  const refreshDashboard = async () => {
    if (!client.getDashboard) return;
    try {
      setDashboard(await client.getDashboard());
    } catch {
      // The rest of the workspace remains usable while the API starts.
    }
  };

  const completeFinancialImport = (
    companyId: string,
    analysis: FinancialAnalysis,
  ) => {
    setCompanies((current) =>
      current.map((company) =>
        company.id === companyId
          ? {
              ...company,
              status: "ready",
              latest_mk_score: analysis.mk_score,
              latest_quality_score: analysis.quality_score,
              latest_safety_score: analysis.safety_score,
            }
          : company,
      ),
    );
    setScores((current) => ({
      ...current,
      [companyId]: analysis.mk_score,
    }));
    setFinancialCompany(null);
    void refreshDashboard();
  };

  const openAnalysis = async (company: Company) => {
    setAnalysisCompany(company);
    setFinancialHistory(null);
    setValuations([]);
    setScoringAnalyses([]);
    setAnalysisError(null);
    setAnalysisLoading(true);
    try {
      const [history, valuationHistory, scoreHistory] = await Promise.all([
        client.getFinancialHistory(company.id),
        client.listValuations(company.id),
        client.listScores(company.id),
      ]);
      setFinancialHistory(history);
      setValuations(valuationHistory);
      setScoringAnalyses(scoreHistory);
    } catch (caughtError) {
      setAnalysisError(
        caughtError instanceof Error
          ? caughtError.message
          : "L’analyse financière n’a pas pu être chargée.",
      );
    } finally {
      setAnalysisLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    client
      .listCompanies()
      .then((records) => {
        if (active) setCompanies(records);
      })
      .catch(() => {
        // The empty state remains useful while the API starts.
      });
    if (client.getDashboard) {
      client
        .getDashboard()
        .then((result) => {
          if (active) setDashboard(result);
        })
        .catch(() => {
          // The dashboard appears as soon as the API is available.
        });
    }
    return () => {
      active = false;
    };
  }, [client]);

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <h1>Vue d’ensemble</h1>
          <div className="topbar__actions">
            <span className="data-status">
              <span className="status-dot" aria-hidden="true" />
              Données prêtes
            </span>
            {client.analyzeWithAI && aiCompanies.length > 0 && (
              <button
                className="button button--secondary"
                onClick={() => setAIAnalystOpen(true)}
              >
                <Sparkles aria-hidden="true" size={18} />
                Interroger l’IA
              </button>
            )}
            <button
              className="button button--primary"
              onClick={() => setImportOpen(true)}
            >
              <Plus aria-hidden="true" size={19} />
              Importer une entreprise
            </button>
          </div>
        </header>
        <SummaryStrip
          companies={companies.length}
          analyses={
            companies.filter((company) => company.status === "ready").length
          }
          favorable={dashboard?.summary.favorable ?? 0}
        />
        <div className="content">
          {dashboard && (
            <DecisionDashboard
              dashboard={dashboard}
              companies={companies}
              onAnalysis={openAnalysis}
            />
          )}
          <CompanyUniverse
            companies={companies}
            scores={scores}
            onImport={() => setImportOpen(true)}
            onFinancialImport={setFinancialCompany}
            onAnalysis={openAnalysis}
          />
          <AnalysisPipeline />
        </div>
        <footer className="statusbar">
          <span className="status-dot" aria-hidden="true" />
          API opérationnelle · PostgreSQL connecté
        </footer>
      </main>
      {isImportOpen && (
        <ImportDrawer
          onClose={() => setImportOpen(false)}
          onSubmit={async (payload) => {
            const company = await client.createCompany(payload);
            setCompanies((current) => [...current, company]);
            setImportOpen(false);
            void refreshDashboard();
          }}
        />
      )}
      {isAIAnalystOpen && client.analyzeWithAI && (
        <AIAnalystDrawer
          companies={aiCompanies}
          onAnalyze={(payload: AIAnalysisPayload) =>
            client.analyzeWithAI!(payload)
          }
          onClose={() => setAIAnalystOpen(false)}
        />
      )}
      {financialCompany && (
        <FinancialDrawer
          company={financialCompany}
          onClose={() => setFinancialCompany(null)}
          onAutomaticSubmit={async () => {
            const analysis = await client.importFinancialsAutomatically(
              financialCompany.id,
            );
            completeFinancialImport(financialCompany.id, analysis);
          }}
          onSubmit={async (payload) => {
            const analysis = await client.importFinancials(
              financialCompany.id,
              payload,
            );
            completeFinancialImport(financialCompany.id, analysis);
          }}
        />
      )}
      {analysisCompany && (
        <AnalysisDrawer
          company={analysisCompany}
          history={financialHistory}
          valuations={valuations}
          scores={scoringAnalyses}
          loading={analysisLoading}
          error={analysisError}
          onCreateValuation={async (payload: ValuationPayload) => {
            const valuation = await client.createValuation(
              analysisCompany.id,
              payload,
            );
            setValuations((current) => [valuation, ...current]);
            return valuation;
          }}
          onCreateScore={async (payload: ScoringPayload) => {
            const score = await client.createScore(
              analysisCompany.id,
              payload,
            );
            setScoringAnalyses((current) => [score, ...current]);
            await refreshDashboard();
            return score;
          }}
          onClose={() => {
            setAnalysisCompany(null);
            setFinancialHistory(null);
            setValuations([]);
            setScoringAnalyses([]);
          }}
        />
      )}
    </div>
  );
}

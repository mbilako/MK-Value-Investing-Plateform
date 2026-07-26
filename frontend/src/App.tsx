import { useEffect, useState } from "react";
import { Plus } from "lucide-react";

import {
  apiClient,
  type Company,
  type CompanyClient,
  type FinancialAnalysis,
  type FinancialHistory,
} from "./api/client";
import { AnalysisDrawer } from "./components/AnalysisDrawer";
import { AnalysisPipeline } from "./components/AnalysisPipeline";
import { CompanyUniverse } from "./components/CompanyUniverse";
import { FinancialDrawer } from "./components/FinancialDrawer";
import { ImportDrawer } from "./components/ImportDrawer";
import { Sidebar } from "./components/Sidebar";
import { SummaryStrip } from "./components/SummaryStrip";

interface AppProps {
  client?: CompanyClient;
}

export function App({ client = apiClient }: AppProps) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isImportOpen, setImportOpen] = useState(false);
  const [financialCompany, setFinancialCompany] = useState<Company | null>(
    null,
  );
  const [scores, setScores] = useState<Record<string, number>>({});
  const [analysisCompany, setAnalysisCompany] = useState<Company | null>(null);
  const [financialHistory, setFinancialHistory] =
    useState<FinancialHistory | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

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
  };

  const openAnalysis = async (company: Company) => {
    setAnalysisCompany(company);
    setFinancialHistory(null);
    setAnalysisError(null);
    setAnalysisLoading(true);
    try {
      setFinancialHistory(await client.getFinancialHistory(company.id));
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
        />
        <div className="content">
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
          }}
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
          loading={analysisLoading}
          error={analysisError}
          onClose={() => {
            setAnalysisCompany(null);
            setFinancialHistory(null);
          }}
        />
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { apiClient, type Company, type CompanyClient } from "./api/client";
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

  const completeFinancialImport = (
    companyId: string,
    mkScore: number,
  ) => {
    setCompanies((current) =>
      current.map((company) =>
        company.id === companyId
          ? {
              ...company,
              status: "ready",
              latest_mk_score: mkScore,
            }
          : company,
      ),
    );
    setScores((current) => ({
      ...current,
      [companyId]: mkScore,
    }));
    setFinancialCompany(null);
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
            completeFinancialImport(
              financialCompany.id,
              analysis.mk_score,
            );
          }}
          onSubmit={async (payload) => {
            const analysis = await client.importFinancials(
              financialCompany.id,
              payload,
            );
            completeFinancialImport(
              financialCompany.id,
              analysis.mk_score,
            );
          }}
        />
      )}
    </div>
  );
}

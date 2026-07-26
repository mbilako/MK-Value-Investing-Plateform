export type CompanyStatus = "pending" | "ready" | "error";

export interface CompanyPayload {
  name: string;
  ticker: string;
  exchange: string;
  country: string;
  currency: string;
}

export interface Company extends CompanyPayload {
  id: string;
  status: CompanyStatus;
  latest_mk_score?: number | null;
  latest_quality_score?: number | null;
  latest_safety_score?: number | null;
}

export interface FinancialPayload {
  fiscal_year: number;
  source: string;
  currency: string;
  revenue: number;
  ebitda: number;
  depreciation_amortization: number;
  ebit: number;
  interest_expense: number;
  operating_cash_flow: number;
  capex: number;
  net_income: number;
  market_cap: number;
  total_assets: number;
  current_assets: number;
  current_liabilities: number;
  financial_debt: number;
  cash: number;
  total_equity: number;
}

export interface FinancialMetric {
  key: string;
  label: string;
  value: number;
  status: "pass" | "review" | "fail";
  source_note: string;
}

export interface FinancialIndicator {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  formula: string;
}

export interface FinancialAnalysis extends FinancialPayload {
  id: string;
  company_id: string;
  metrics: FinancialMetric[];
  indicators: FinancialIndicator[];
  mk_score: number;
  quality_score: number;
  safety_score: number;
  created_at: string;
}

export interface FinancialTrend {
  periods: number;
  first_year: number | null;
  last_year: number | null;
  revenue_cagr: number | null;
  net_income_cagr: number | null;
  free_cash_flow_cagr: number | null;
}

export interface FinancialHistory {
  company_id: string;
  snapshots: FinancialAnalysis[];
  trend: FinancialTrend;
}

export interface CompanyClient {
  listCompanies(): Promise<Company[]>;
  createCompany(payload: CompanyPayload): Promise<Company>;
  importFinancials(
    companyId: string,
    payload: FinancialPayload,
  ): Promise<FinancialAnalysis>;
  importFinancialsAutomatically(companyId: string): Promise<FinancialAnalysis>;
  getFinancialHistory(companyId: string): Promise<FinancialHistory>;
}

const apiUrl = import.meta.env.VITE_API_URL ?? "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      errorBody?.detail ?? `API request failed with status ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

export const apiClient: CompanyClient = {
  listCompanies: () => request<Company[]>("/companies"),
  createCompany: (payload) =>
    request<Company>("/companies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  importFinancials: (companyId, payload) =>
    request<FinancialAnalysis>(`/companies/${companyId}/financials`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  importFinancialsAutomatically: (companyId) =>
    request<FinancialAnalysis>(
      `/companies/${companyId}/financials/automatic`,
      { method: "POST" },
    ),
  getFinancialHistory: (companyId) =>
    request<FinancialHistory>(`/companies/${companyId}/financials`),
};

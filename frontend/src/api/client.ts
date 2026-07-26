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

export interface FinancialAnalysis extends FinancialPayload {
  id: string;
  company_id: string;
  metrics: FinancialMetric[];
  mk_score: number;
  created_at: string;
}

export interface CompanyClient {
  listCompanies(): Promise<Company[]>;
  createCompany(payload: CompanyPayload): Promise<Company>;
  importFinancials(
    companyId: string,
    payload: FinancialPayload,
  ): Promise<FinancialAnalysis>;
  importFinancialsAutomatically(companyId: string): Promise<FinancialAnalysis>;
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
};

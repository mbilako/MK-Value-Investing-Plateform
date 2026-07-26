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

export interface ValuationAssumptions {
  growth_rate: number;
  terminal_growth_rate: number;
  cost_of_equity: number;
  wacc: number;
  tax_rate: number;
  projection_years: number;
  target_pe: number;
  corporate_bond_yield: number;
  margin_of_safety: number;
}

export interface ValuationPayload {
  fiscal_year: number;
  assumptions: ValuationAssumptions;
}

export interface ValuationMethod {
  key: string;
  label: string;
  value: number | null;
  category: "intrinsic" | "relative" | "proxy";
  formula: string;
  base_metric: string;
  note: string;
}

export interface ValuationAnalysis {
  id: string;
  company_id: string;
  financial_snapshot_id: string;
  fiscal_year: number;
  currency: string;
  market_cap: number;
  assumptions: ValuationAssumptions;
  methods: ValuationMethod[];
  central_estimate: number | null;
  margin_of_safety_value: number | null;
  market_gap: number | null;
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
  getFinancialHistory(companyId: string): Promise<FinancialHistory>;
  listValuations(companyId: string): Promise<ValuationAnalysis[]>;
  createValuation(
    companyId: string,
    payload: ValuationPayload,
  ): Promise<ValuationAnalysis>;
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
  listValuations: (companyId) =>
    request<ValuationAnalysis[]>(`/companies/${companyId}/valuations`),
  createValuation: (companyId, payload) =>
    request<ValuationAnalysis>(`/companies/${companyId}/valuations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

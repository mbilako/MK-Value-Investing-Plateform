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

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
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

export interface ScoringPayload {
  fiscal_year: number;
  valuation_id: string;
}

export interface ScoringComponent {
  key: string;
  label: string;
  score: number;
  weight: number;
  contribution: number;
  formula: string;
  note: string;
}

export interface ScoringInsight {
  key: string;
  tone: "positive" | "neutral" | "caution";
  label: string;
}

export interface ScoringAnalysis {
  id: string;
  company_id: string;
  financial_snapshot_id: string;
  valuation_analysis_id: string;
  fiscal_year: number;
  components: ScoringComponent[];
  insights: ScoringInsight[];
  global_score: number;
  signal: "favorable" | "watch" | "caution";
  signal_label: string;
  created_at: string;
}

export type DashboardSignal =
  | "favorable"
  | "watch"
  | "caution"
  | "unscored";

export interface DashboardSummary {
  companies: number;
  ready: number;
  scored: number;
  favorable: number;
  watch: number;
  caution: number;
  unscored: number;
}

export interface DashboardDistribution {
  signal: DashboardSignal;
  label: string;
  count: number;
}

export interface DashboardWeakestComponent {
  key: string;
  label: string;
  score: number;
}

export interface DashboardCompany {
  company_id: string;
  name: string;
  ticker: string;
  exchange: string;
  country: string;
  status: CompanyStatus;
  fiscal_year: number | null;
  global_score: number | null;
  signal: DashboardSignal;
  signal_label: string;
  market_gap: number | null;
  weakest_component: DashboardWeakestComponent | null;
  updated_at: string | null;
}

export interface Dashboard {
  summary: DashboardSummary;
  distribution: DashboardDistribution[];
  companies: DashboardCompany[];
}

export type AIAnalysisMode = "summary" | "comparison" | "question";

export interface AIAnalysisPayload {
  mode: AIAnalysisMode;
  company_id: string;
  comparison_company_id?: string;
  question?: string;
}

export interface AIAnalysisSource {
  id: string;
  company_id: string;
  kind: "financial" | "valuation" | "scoring";
  label: string;
  fiscal_year: number;
  created_at: string;
}

export interface AIAnalysisEvidence {
  title: string;
  finding: string;
  source_ids: string[];
}

export interface AIAnalysis {
  mode: AIAnalysisMode;
  headline: string;
  conclusion: string;
  evidence: AIAnalysisEvidence[];
  risks: string[];
  missing_information: string[];
  sources: AIAnalysisSource[];
  model: string;
  generated_at: string;
  disclaimer: string;
}

export interface CompanyClient {
  getCurrentUser(): Promise<User>;
  register(credentials: AuthCredentials): Promise<User>;
  login(credentials: AuthCredentials): Promise<User>;
  logout(): Promise<void>;
  onUnauthorized(handler: () => void): () => void;
  listCompanies(): Promise<Company[]>;
  getDashboard?(): Promise<Dashboard>;
  analyzeWithAI?(payload: AIAnalysisPayload): Promise<AIAnalysis>;
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
  listScores(companyId: string): Promise<ScoringAnalysis[]>;
  createScore(
    companyId: string,
    payload: ScoringPayload,
  ): Promise<ScoringAnalysis>;
}

const apiUrl = import.meta.env.VITE_API_URL ?? "/api/v1";

export function createApiClient(): CompanyClient {
  const unauthorizedListeners = new Set<() => void>();

  async function request<T>(
    path: string,
    options?: RequestInit,
    notifyUnauthorized = true,
  ): Promise<T> {
    const response = await fetch(`${apiUrl}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    if (!response.ok) {
      const errorBody = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;
      if (response.status === 401 && notifyUnauthorized) {
        unauthorizedListeners.forEach((listener) => listener());
      }
      throw new ApiError(
        response.status,
        errorBody?.detail ?? `API request failed with status ${response.status}`,
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  }

  return {
    getCurrentUser: () => request<User>("/auth/me", undefined, false),
    register: (credentials) =>
      request<User>(
        "/auth/register",
        { method: "POST", body: JSON.stringify(credentials) },
        false,
      ),
    login: (credentials) =>
      request<User>(
        "/auth/login",
        { method: "POST", body: JSON.stringify(credentials) },
        false,
      ),
    logout: () => request<void>("/auth/logout", { method: "POST" }, false),
    onUnauthorized: (handler) => {
      unauthorizedListeners.add(handler);
      return () => unauthorizedListeners.delete(handler);
    },
    listCompanies: () => request<Company[]>("/companies"),
    getDashboard: () => request<Dashboard>("/dashboard"),
    analyzeWithAI: (payload) =>
      request<AIAnalysis>("/ai/analyses", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
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
    listScores: (companyId) => request<ScoringAnalysis[]>(`/companies/${companyId}/scores`),
    createScore: (companyId, payload) =>
      request<ScoringAnalysis>(`/companies/${companyId}/scores`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  };
}

export const apiClient = createApiClient();

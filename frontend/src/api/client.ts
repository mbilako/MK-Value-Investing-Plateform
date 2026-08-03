export type CompanyStatus = "pending" | "ready" | "error";

export interface CompanyPayload {
  name: string;
  ticker: string;
  exchange: string;
  country: string;
  currency: string;
  isin?: string | null;
  cik?: string | null;
  lei?: string | null;
  provider_symbols?: Record<string, string>;
  index_memberships?: string[];
}

export interface Company extends CompanyPayload {
  id: string;
  status: CompanyStatus;
  latest_mk_score?: number | null;
  latest_quality_score?: number | null;
  latest_safety_score?: number | null;
  archived_at?: string | null;
}

export interface IndexSummary {
  code: string;
  name: string;
  isin: string;
  market: string;
  provider: string;
}

export interface IndexConstituent {
  name: string;
  isin: string;
  mic: string;
  trading_location: string;
  country: string;
}

export interface IndexComposition extends IndexSummary {
  as_of: string | null;
  source_url: string;
  constituents: IndexConstituent[];
}

export interface IndexCompanySelection extends IndexConstituent {
  index_code: string;
}

export interface IndexBulkAddResult {
  created: Company[];
  existing: Company[];
  errors: Array<{ name: string; isin: string; detail: string }>;
}

export interface User {
  id: string;
  email: string;
  created_at: string;
  mfa_enabled: boolean;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthMessage {
  message: string;
}

export interface MfaChallenge {
  mfa_required: true;
  challenge_token: string;
  expires_at: string;
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
  expires_at: string;
}

export interface MfaRecoveryCodes {
  recovery_codes: string[];
}

export interface AccountSession {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string | null;
  current: boolean;
}

export type LoginResult = User | MfaChallenge;

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
  analysis_profile?: "standard" | "financial";
  revenue: number;
  ebitda: number | null;
  depreciation_amortization: number | null;
  ebit: number | null;
  interest_expense: number | null;
  operating_cash_flow: number | null;
  capex: number | null;
  net_income: number;
  pretax_income?: number | null;
  market_cap: number;
  closing_price?: number | null;
  shares_outstanding?: number | null;
  treasury_stock_value?: number | null;
  total_assets: number;
  current_assets: number | null;
  current_liabilities: number | null;
  financial_debt: number | null;
  cash: number | null;
  total_equity: number;
  investing_cash_flow?: number | null;
}

export interface FinancialMetric {
  key: string;
  label: string;
  value: number | null;
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
  mk_score: number | null;
  quality_score: number | null;
  safety_score: number | null;
  created_at: string;
}

export interface FinancialTrend {
  periods: number;
  first_year: number | null;
  last_year: number | null;
  revenue_cagr: number | null;
  net_income_cagr: number | null;
  free_cash_flow_cagr: number | null;
  operating_income_cagr?: number | null;
  pretax_income_cagr?: number | null;
  pe_annual_change?: number | null;
  roe_annual_change?: number | null;
  current_ratio_annual_change?: number | null;
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
  register(credentials: AuthCredentials): Promise<AuthMessage>;
  login(credentials: AuthCredentials): Promise<LoginResult>;
  verifyMfa(challengeToken: string, code: string): Promise<User>;
  setupMfa(): Promise<MfaSetup>;
  confirmMfa(code: string): Promise<MfaRecoveryCodes>;
  disableMfa(code: string): Promise<void>;
  listSessions(): Promise<AccountSession[]>;
  revokeSession(sessionId: string): Promise<void>;
  revokeOtherSessions(): Promise<void>;
  logout(): Promise<void>;
  verifyEmail(token: string): Promise<void>;
  resendVerification(email: string): Promise<AuthMessage>;
  requestPasswordReset(email: string): Promise<AuthMessage>;
  confirmPasswordReset(token: string, password: string): Promise<void>;
  onUnauthorized(handler: () => void): () => void;
  listCompanies(): Promise<Company[]>;
  getDashboard?(): Promise<Dashboard>;
  analyzeWithAI?(payload: AIAnalysisPayload): Promise<AIAnalysis>;
  createCompany(payload: CompanyPayload): Promise<Company>;
  updateCompany(id: string, payload: Partial<CompanyPayload>): Promise<Company>;
  archiveCompany(id: string): Promise<Company>;
  restoreCompany(id: string): Promise<Company>;
  deleteCompany(id: string): Promise<void>;
  listIndices(): Promise<IndexSummary[]>;
  getIndex(code: string): Promise<IndexComposition>;
  addIndexCompanies(companies: IndexCompanySelection[]): Promise<IndexBulkAddResult>;
  importFinancials(
    companyId: string,
    payload: FinancialPayload,
  ): Promise<FinancialAnalysis>;
  importFinancialsAutomatically(companyId: string): Promise<FinancialHistory>;
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

function formatErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === "string") {
    return detail || undefined;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map(formatErrorDetail)
      .filter((message): message is string => message !== undefined);
    return messages.length > 0 ? messages.join("; ") : undefined;
  }
  if (typeof detail === "object" && detail !== null && "msg" in detail) {
    return formatErrorDetail((detail as { msg: unknown }).msg);
  }
  return undefined;
}

function getErrorMessage(errorBody: unknown, status: number): string {
  if (
    typeof errorBody === "object" &&
    errorBody !== null &&
    "detail" in errorBody
  ) {
    const detailMessage = formatErrorDetail(
      (errorBody as { detail: unknown }).detail,
    );
    if (detailMessage !== undefined) {
      return detailMessage;
    }
  }
  return `API request failed with status ${status}`;
}

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
      const errorBody: unknown = await response.json().catch(() => null);
      if (response.status === 401 && notifyUnauthorized) {
        unauthorizedListeners.forEach((listener) => listener());
      }
      throw new ApiError(
        response.status,
        getErrorMessage(errorBody, response.status),
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
      request<AuthMessage>(
        "/auth/register",
        { method: "POST", body: JSON.stringify(credentials) },
        false,
      ),
    login: (credentials) =>
      request<LoginResult>(
        "/auth/login",
        { method: "POST", body: JSON.stringify(credentials) },
        false,
      ),
    verifyMfa: (challengeToken, code) =>
      request<User>(
        "/auth/mfa/verify",
        {
          method: "POST",
          body: JSON.stringify({ challenge_token: challengeToken, code }),
        },
        false,
      ),
    setupMfa: () => request<MfaSetup>("/auth/mfa/setup", { method: "POST" }),
    confirmMfa: (code) =>
      request<MfaRecoveryCodes>("/auth/mfa/confirm", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    disableMfa: (code) =>
      request<void>("/auth/mfa/disable", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    listSessions: () => request<AccountSession[]>("/auth/sessions"),
    revokeSession: (sessionId) =>
      request<void>(`/auth/sessions/${sessionId}`, { method: "DELETE" }),
    revokeOtherSessions: () =>
      request<void>("/auth/sessions/revoke-other", { method: "POST" }),
    logout: () => request<void>("/auth/logout", { method: "POST" }, false),
    verifyEmail: (token) =>
      request<void>(
        "/auth/verify-email",
        { method: "POST", body: JSON.stringify({ token }) },
        false,
      ),
    resendVerification: (email) =>
      request<AuthMessage>(
        "/auth/resend-verification",
        { method: "POST", body: JSON.stringify({ email }) },
        false,
      ),
    requestPasswordReset: (email) =>
      request<AuthMessage>(
        "/auth/password-reset/request",
        { method: "POST", body: JSON.stringify({ email }) },
        false,
      ),
    confirmPasswordReset: (token, password) =>
      request<void>(
        "/auth/password-reset/confirm",
        { method: "POST", body: JSON.stringify({ token, password }) },
        false,
      ),
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
    updateCompany: (id, payload) =>
      request<Company>(`/companies/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    archiveCompany: (id) =>
      request<Company>(`/companies/${id}/archive`, { method: "POST" }),
    restoreCompany: (id) =>
      request<Company>(`/companies/${id}/restore`, { method: "POST" }),
    deleteCompany: (id) =>
      request<void>(`/companies/${id}`, { method: "DELETE" }),
    listIndices: () => request<IndexSummary[]>("/indices"),
    getIndex: (code) => request<IndexComposition>(`/indices/${code}`),
    addIndexCompanies: (companies) =>
      request<IndexBulkAddResult>("/indices/companies/bulk", {
        method: "POST",
        body: JSON.stringify({ companies }),
      }),
    importFinancials: (companyId, payload) =>
      request<FinancialAnalysis>(`/companies/${companyId}/financials`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    importFinancialsAutomatically: (companyId) =>
      request<FinancialHistory>(
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

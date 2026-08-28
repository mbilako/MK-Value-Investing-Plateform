export type CompanyStatus = "pending" | "partial" | "ready" | "error";

export interface CompanyPayload {
  name: string;
  ticker: string;
  exchange: string;
  country: string;
  currency: string;
  sector?: string | null;
  industry?: string | null;
  business_summary?: string | null;
  isin?: string | null;
  cik?: string | null;
  lei?: string | null;
  provider_symbols?: Record<string, string>;
  index_memberships?: string[];
  is_favorite?: boolean;
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
  isin: string | null;
  market: string;
  provider: string;
  region?: string;
  country?: string;
  kind?: "broad" | "sector";
  sector?: string | null;
}

export interface CompanyBulkDeleteResult {
  deleted_ids: string[];
}

export interface IndexConstituent {
  name: string;
  isin?: string | null;
  ticker?: string | null;
  mic: string;
  trading_location: string;
  country: string;
  currency?: string;
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
  errors: Array<{
    name: string;
    isin?: string | null;
    ticker?: string | null;
    detail: string;
  }>;
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
  ebitda_cagr?: number | null;
  pe_annual_change?: number | null;
  roe_annual_change?: number | null;
  current_ratio_annual_change?: number | null;
}

export interface FinancialHistory {
  company_id: string;
  snapshots: FinancialAnalysis[];
  trend: FinancialTrend;
  price_history?: PriceHistory | null;
}

export interface PricePoint {
  date: string;
  close: number;
  adjusted_close: number | null;
}

export interface PriceHistory {
  company_id: string;
  currency: string;
  source: string;
  points: PricePoint[];
  updated_at: string | null;
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

export type ScreenerStatus =
  | "leader"
  | "candidate"
  | "secondary"
  | "insufficient_data"
  | "insufficient_peers"
  | "unclassified";

export interface ScreenerMetric {
  key: string;
  label: string;
  value: number;
  sector_median: number;
  percentile: number;
  weight: number;
  higher_is_better: boolean;
}

export interface ScreenerCompany {
  company_id: string;
  name: string;
  ticker: string;
  sector: string | null;
  sector_label: string | null;
  industry: string | null;
  is_favorite: boolean;
  index_memberships: string[];
  fiscal_year: number | null;
  absolute_score: number | null;
  sector_score: number | null;
  sector_rank: number | null;
  peer_count: number;
  data_coverage: number;
  status: ScreenerStatus;
  status_label: string;
  explanation: string;
  metrics: ScreenerMetric[];
  updated_at: string | null;
}

export interface Screener {
  summary: {
    companies: number;
    classified: number;
    eligible: number;
    leaders: number;
    sectors: number;
    min_peer_count: number;
  };
  sectors: string[];
  companies: ScreenerCompany[];
  disclaimer: string;
}

export interface ScreenerPreparation {
  requested: number;
  processed: number;
  classified: number;
  imported: number;
  unchanged: number;
  failed: number;
  remaining: number;
  items: Array<{
    company_id: string;
    name: string;
    ticker: string;
    status:
      | "classified"
      | "imported"
      | "unchanged"
      | "unclassified"
      | "failed";
    sector: string | null;
    industry: string | null;
    detail: string;
  }>;
}

export type MarketScanStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface NationalMarket {
  code: string;
  name: string;
  region: string;
  currency: string;
  exchanges: string[];
}

export interface MarketScanCriteria {
  market: "US" | "INDEX" | "COUNTRY" | "MKVIP";
  index_code: string | null;
  country_code: string | null;
  exchanges: Array<"NASDAQ" | "NYSE" | "AMEX">;
  years: number;
  performance_direction: "decline" | "gain" | "any";
  minimum_decline_pct: number;
  minimum_market_cap: number | null;
  maximum_market_cap: number | null;
  maximum_pe_ratio: number | null;
  maximum_price_to_book: number | null;
  minimum_dividend_yield_pct: number | null;
  minimum_mk_score: number | null;
  minimum_annualized_return_pct: number | null;
  maximum_volatility_pct: number | null;
  minimum_drawdown_pct: number | null;
  sort_by: "performance" | "annualized_return" | "volatility" | "max_drawdown" | "market_cap" | "pe_ratio" | "price_to_book" | "dividend_yield" | "mk_score";
  sort_direction: "asc" | "desc";
  result_limit: number | null;
  ordinary_shares_only: boolean;
}

export interface MarketScanResult {
  id: string;
  ticker: string;
  name: string;
  exchange: string;
  country: string;
  currency: string;
  market_cap: number | null;
  pe_ratio: number | null;
  price_to_book: number | null;
  dividend_yield_pct: number | null;
  mk_score: number | null;
  start_date: string;
  end_date: string;
  start_price: number;
  end_price: number;
  performance_pct: number;
  annualized_return_pct: number | null;
  volatility_pct: number | null;
  max_drawdown_pct: number | null;
  price_source: string;
}

export interface MarketScan {
  id: string;
  status: MarketScanStatus;
  criteria: MarketScanCriteria;
  request_text: string | null;
  universe_source: string;
  price_source: string;
  total_securities: number;
  processed_securities: number;
  matched_securities: number;
  failed_securities: number;
  insufficient_history_securities: number;
  progress_pct: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  results: MarketScanResult[];
}

export type MarketScanListItem = Omit<
  MarketScan,
  "universe_source" | "price_source" | "results"
>;

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
  getScreener?(): Promise<Screener>;
  prepareScreener?(payload: {
    company_ids?: string[];
    import_financials?: boolean;
    limit?: number;
  }): Promise<ScreenerPreparation>;
  analyzeWithAI?(payload: AIAnalysisPayload): Promise<AIAnalysis>;
  listMarketScans?(): Promise<MarketScanListItem[]>;
  listNationalMarkets?(): Promise<NationalMarket[]>;
  createMarketScan?(criteria: MarketScanCriteria): Promise<MarketScan>;
  createMarketScanFromQuestion?(question: string): Promise<MarketScan>;
  getMarketScan?(id: string): Promise<MarketScan>;
  retryMarketScan?(id: string): Promise<MarketScan>;
  cancelMarketScan?(id: string): Promise<MarketScan>;
  exportMarketScan?(id: string): Promise<void>;
  createCompany(payload: CompanyPayload): Promise<Company>;
  updateCompany(id: string, payload: Partial<CompanyPayload>): Promise<Company>;
  archiveCompany(id: string): Promise<Company>;
  restoreCompany(id: string): Promise<Company>;
  deleteCompany(id: string): Promise<void>;
  deleteCompanies(ids: string[]): Promise<CompanyBulkDeleteResult>;
  listIndices(): Promise<IndexSummary[]>;
  getIndex(code: string): Promise<IndexComposition>;
  addIndexCompanies(companies: IndexCompanySelection[]): Promise<IndexBulkAddResult>;
  importFinancials(
    companyId: string,
    payload: FinancialPayload,
  ): Promise<FinancialAnalysis>;
  importFinancialsAutomatically(companyId: string): Promise<FinancialHistory>;
  getFinancialHistory(companyId: string): Promise<FinancialHistory>;
  importPriceHistoryAutomatically(companyId: string): Promise<PriceHistory>;
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

  async function download(path: string): Promise<void> {
    const response = await fetch(`${apiUrl}${path}`, { credentials: "include" });
    if (!response.ok) {
      const errorBody: unknown = await response.json().catch(() => null);
      throw new ApiError(response.status, getErrorMessage(errorBody, response.status));
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1]
      ?? "MK-VIP_scan_marche.xlsx";
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
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
    getScreener: () => request<Screener>("/screener"),
    prepareScreener: (payload) =>
      request<ScreenerPreparation>("/screener/prepare", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
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
    deleteCompanies: (ids) =>
      request<CompanyBulkDeleteResult>("/companies/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ company_ids: ids }),
      }),
    listMarketScans: () => request<MarketScanListItem[]>("/market-scans"),
    listNationalMarkets: () => request<NationalMarket[]>("/market-scans/national-markets"),
    createMarketScan: (criteria) =>
      request<MarketScan>("/market-scans", {
        method: "POST",
        body: JSON.stringify({ criteria }),
      }),
    createMarketScanFromQuestion: (question) =>
      request<MarketScan>("/market-scans/from-question", {
        method: "POST",
        body: JSON.stringify({ question }),
      }),
    getMarketScan: (id) => request<MarketScan>(`/market-scans/${id}`),
    retryMarketScan: (id) =>
      request<MarketScan>(`/market-scans/${id}/retry`, { method: "POST" }),
    cancelMarketScan: (id) =>
      request<MarketScan>(`/market-scans/${id}/cancel`, { method: "POST" }),
    exportMarketScan: (id) => download(`/market-scans/${id}/export.xlsx`),
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
    importPriceHistoryAutomatically: (companyId) =>
      request<PriceHistory>(
        `/companies/${companyId}/financials/prices/automatic`,
        { method: "POST" },
      ),
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

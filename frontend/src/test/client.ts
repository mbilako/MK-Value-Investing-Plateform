import type { AuthMessage, CompanyClient, User } from "../api/client";

export const testUser: User = {
  id: "user-1",
  email: "investor@example.com",
  created_at: "2026-07-26T10:00:00Z",
  mfa_enabled: false,
};

const testAuthMessage: AuthMessage = {
  message: "Demande prise en compte.",
};

export function createTestClient(
  overrides: Partial<CompanyClient> = {},
): CompanyClient {
  return {
    getCurrentUser: async () => testUser,
    register: async () => testAuthMessage,
    login: async () => testUser,
    verifyMfa: async () => testUser,
    setupMfa: async () => ({
      secret: "JBSWY3DPEHPK3PXP",
      otpauth_uri: "otpauth://totp/MK-VIP:investor@example.com",
      expires_at: "2026-07-26T10:10:00Z",
    }),
    confirmMfa: async () => ({ recovery_codes: [] }),
    disableMfa: async () => undefined,
    listSessions: async () => [],
    revokeSession: async () => undefined,
    revokeOtherSessions: async () => undefined,
    logout: async () => undefined,
    verifyEmail: async () => undefined,
    resendVerification: async () => testAuthMessage,
    requestPasswordReset: async () => testAuthMessage,
    confirmPasswordReset: async () => undefined,
    onUnauthorized: () => () => undefined,
    listCompanies: async () => [],
    createCompany: async (payload) => ({
      id: "company-created",
      status: "pending",
      ...payload,
    }),
    updateCompany: async (id, payload) => ({
      id,
      name: "Entreprise test",
      ticker: "TEST.PA",
      exchange: "Euronext Paris",
      country: "France",
      currency: "EUR",
      status: "pending",
      ...payload,
    }),
    archiveCompany: async (id) => ({
      id,
      name: "Entreprise test",
      ticker: "TEST.PA",
      exchange: "Euronext Paris",
      country: "France",
      currency: "EUR",
      status: "pending",
      archived_at: new Date().toISOString(),
    }),
    restoreCompany: async (id) => ({
      id,
      name: "Entreprise test",
      ticker: "TEST.PA",
      exchange: "Euronext Paris",
      country: "France",
      currency: "EUR",
      status: "pending",
      archived_at: null,
    }),
    deleteCompany: async () => undefined,
    listIndices: async () => [],
    getIndex: async () => {
      throw new Error("Indice non configuré dans ce test.");
    },
    addIndexCompanies: async () => ({ created: [], existing: [], errors: [] }),
    importFinancials: async () => {
      throw new Error("Import financier non configuré dans ce test.");
    },
    importFinancialsAutomatically: async () => {
      throw new Error("Import automatique non configuré dans ce test.");
    },
    getFinancialHistory: async () => {
      throw new Error("Historique financier non configuré dans ce test.");
    },
    listValuations: async () => [],
    createValuation: async () => {
      throw new Error("Valorisation non configurée dans ce test.");
    },
    listScores: async () => [],
    createScore: async () => {
      throw new Error("Scoring non configuré dans ce test.");
    },
    ...overrides,
  };
}

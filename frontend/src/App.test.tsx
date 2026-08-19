import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { ApiError } from "./api/client";
import type {
  AIAnalysisPayload,
  CompanyClient,
} from "./api/client";
import { createTestClient, testUser } from "./test/client";

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
});

const unusedAutomaticImport = async () => {
  throw new Error("Import automatique non utilisé dans ce scénario.");
};

const unusedFinancialHistory = async () => {
  throw new Error("Historique financier non utilisé dans ce scénario.");
};

const unusedValuations = async () => [];

const unusedCreateValuation = async () => {
  throw new Error("Valorisation non utilisée dans ce scénario.");
};

const unusedScores = async () => [];

const unusedCreateScore = async () => {
  throw new Error("Scoring non utilisé dans ce scénario.");
};

describe("MK-VIP authentication", () => {
  it("shows a neutral loader while checking the existing session", () => {
    const client = createTestClient({
      getCurrentUser: () => new Promise(() => undefined),
    });

    render(<App client={client} />);

    expect(
      screen.getByText("Vérification de votre session…"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Vue d’ensemble")).not.toBeInTheDocument();
  });

  it("registers and waits for email verification without opening the workspace", async () => {
    const user = userEvent.setup();
    const register = vi.fn().mockResolvedValue({
      message: "Consulte ta boîte email pour vérifier ton adresse.",
    });
    const listCompanies = vi.fn().mockResolvedValue([]);
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      register,
      listCompanies,
    });

    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", { name: "Créer un compte" }),
    );
    await user.type(
      screen.getByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(
      screen.getByLabelText("Mot de passe"),
      "correct horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Créer mon compte" }),
    );

    expect(register).toHaveBeenCalledWith({
      email: "investor@example.com",
      password: "correct horse battery",
    });
    const resultHeading = await screen.findByRole("heading", {
      name: "Vérifie ta boîte email",
    });
    expect(resultHeading).toHaveFocus();
    expect(listCompanies).not.toHaveBeenCalled();
  });

  it("requests a password reset and announces the generic result", async () => {
    const user = userEvent.setup();
    const message =
      "Si un compte correspond à cette adresse, un email a été envoyé.";
    const requestPasswordReset = vi.fn().mockResolvedValue({ message });
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      requestPasswordReset,
    });

    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", { name: "Mot de passe oublié ?" }),
    );
    await user.type(
      screen.getByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.click(
      screen.getByRole("button", { name: "Envoyer le lien" }),
    );

    expect(requestPasswordReset).toHaveBeenCalledWith(
      "investor@example.com",
    );
    const result = await screen.findByText(message);
    expect(result).toHaveAttribute("aria-live", "polite");
    expect(result).toHaveFocus();
  });

  it("verifies an email link before any session restoration", async () => {
    window.location.hash = "#verify-email=verification-token";
    const verifyEmail = vi.fn().mockResolvedValue(undefined);
    const getCurrentUser = vi.fn().mockResolvedValue(testUser);

    render(
      <App client={createTestClient({ verifyEmail, getCurrentUser })} />,
    );

    expect(window.location.hash).toBe("");
    expect(getCurrentUser).not.toHaveBeenCalled();
    expect(verifyEmail).toHaveBeenCalledOnce();
    expect(verifyEmail).toHaveBeenCalledWith("verification-token");
    const resultHeading = await screen.findByRole("heading", {
      name: "Adresse vérifiée",
    });
    expect(resultHeading).toHaveFocus();
    expect(screen.queryByText("Vue d’ensemble")).not.toBeInTheDocument();
  });

  it("does not replay a consumed verification link after login and logout", async () => {
    window.location.hash = "#verify-email=verification-token";
    const verifyEmail = vi.fn().mockResolvedValue(undefined);
    const logout = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <App client={createTestClient({ verifyEmail, logout })} />,
    );

    await screen.findByRole("heading", { name: "Adresse vérifiée" });
    await user.click(
      screen.getByRole("button", { name: "Retour à la connexion" }),
    );
    await user.type(
      screen.getByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    await user.click(
      await screen.findByRole("button", { name: "Se déconnecter" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Se connecter" }),
    ).toBeInTheDocument();
    expect(verifyEmail).toHaveBeenCalledOnce();
  });

  it("confirms a password reset link with two matching passwords", async () => {
    window.location.hash = "#reset-password=reset-token";
    const confirmPasswordReset = vi.fn().mockResolvedValue(undefined);
    const getCurrentUser = vi.fn().mockResolvedValue(testUser);
    const user = userEvent.setup();

    render(
      <App
        client={createTestClient({
          confirmPasswordReset,
          getCurrentUser,
        })}
      />,
    );

    expect(window.location.hash).toBe("");
    expect(getCurrentUser).not.toHaveBeenCalled();
    await user.type(
      screen.getByLabelText("Nouveau mot de passe"),
      "correct horse battery",
    );
    await user.type(
      screen.getByLabelText("Confirmer le mot de passe"),
      "correct horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Mettre à jour le mot de passe" }),
    );

    expect(confirmPasswordReset).toHaveBeenCalledWith(
      "reset-token",
      "correct horse battery",
    );
    const resultHeading = await screen.findByRole("heading", {
      name: "Mot de passe mis à jour",
    });
    expect(resultHeading).toHaveFocus();
  });

  it("does not restore a consumed reset link after login and logout", async () => {
    window.location.hash = "#reset-password=reset-token";
    const confirmPasswordReset = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <App client={createTestClient({ confirmPasswordReset })} />,
    );

    await user.type(
      screen.getByLabelText("Nouveau mot de passe"),
      "correct horse battery",
    );
    await user.type(
      screen.getByLabelText("Confirmer le mot de passe"),
      "correct horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Mettre à jour le mot de passe" }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Retour à la connexion",
      }),
    );
    await user.type(
      screen.getByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    await user.click(
      await screen.findByRole("button", { name: "Se déconnecter" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Se connecter" }),
    ).toBeInTheDocument();
    expect(confirmPasswordReset).toHaveBeenCalledOnce();
  });

  it("rejects two different passwords without consuming the reset link", async () => {
    window.location.hash = "#reset-password=reset-token";
    const confirmPasswordReset = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <App client={createTestClient({ confirmPasswordReset })} />,
    );

    await user.type(
      screen.getByLabelText("Nouveau mot de passe"),
      "correct horse battery",
    );
    await user.type(
      screen.getByLabelText("Confirmer le mot de passe"),
      "different horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Mettre à jour le mot de passe" }),
    );

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent(
      "Les mots de passe doivent être identiques.",
    );
    expect(error).toHaveFocus();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("lets the user leave an invalid password-reset link", async () => {
    window.location.hash = "#reset-password=invalid-token";
    const confirmPasswordReset = vi.fn().mockRejectedValue(
      new ApiError(400, "Jeton de réinitialisation invalide."),
    );
    const user = userEvent.setup();

    render(<App client={createTestClient({ confirmPasswordReset })} />);

    await user.type(
      screen.getByLabelText("Nouveau mot de passe"),
      "correct horse battery",
    );
    await user.type(
      screen.getByLabelText("Confirmer le mot de passe"),
      "correct horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Mettre à jour le mot de passe" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Jeton de réinitialisation invalide.",
    );
    await user.click(
      screen.getByRole("button", { name: "Retour à la connexion" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Se connecter" }),
    ).toBeInTheDocument();
  });

  it("offers verification email resend after an unverified login", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockRejectedValue(
      new ApiError(
        403,
        "Vérifie ton adresse email avant de te connecter.",
      ),
    );
    const resendVerification = vi.fn().mockResolvedValue({
      message: "Un nouvel email de vérification a été envoyé.",
    });
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      login,
      resendVerification,
    });

    render(<App client={client} />);

    await user.type(
      await screen.findByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveFocus();
    const resendButton = screen.getByRole("button", {
      name: "Renvoyer l’email de vérification",
    });
    await user.click(resendButton);

    expect(resendVerification).toHaveBeenCalledWith(
      "investor@example.com",
    );
    expect(
      await screen.findByRole("heading", {
        name: "Vérifie ta boîte email",
      }),
    ).toHaveFocus();
  });

  it("returns focus after a verification resend with an unchanged message", async () => {
    const user = userEvent.setup();
    const message = "Consulte ta boîte email pour vérifier ton adresse.";
    const register = vi.fn().mockResolvedValue({ message });
    const resendVerification = vi.fn().mockResolvedValue({ message });
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      register,
      resendVerification,
    });

    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", { name: "Créer un compte" }),
    );
    await user.type(
      screen.getByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(
      screen.getByLabelText("Mot de passe"),
      "correct horse battery",
    );
    await user.click(
      screen.getByRole("button", { name: "Créer mon compte" }),
    );
    const heading = await screen.findByRole("heading", {
      name: "Vérifie ta boîte email",
    });
    const resend = screen.getByRole("button", {
      name: "Renvoyer l’email",
    });
    await user.click(resend);

    expect(resendVerification).toHaveBeenCalledOnce();
    expect(heading).toHaveFocus();
  });

  it("disables every credential control while authentication is pending", async () => {
    const user = userEvent.setup();
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      login: () => new Promise(() => undefined),
    });

    render(<App client={client} />);

    const email = await screen.findByLabelText("Adresse email");
    const password = screen.getByLabelText("Mot de passe");
    await user.type(email, "investor@example.com");
    await user.type(password, "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(email).toBeDisabled();
    expect(password).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Veuillez patienter…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Mot de passe oublié ?" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Créer un compte" }),
    ).toBeDisabled();
  });

  it("completes an MFA challenge before opening the workspace", async () => {
    const user = userEvent.setup();
    const challenge = {
      mfa_required: true as const,
      challenge_token: "challenge-token",
      expires_at: "2026-07-26T10:05:00Z",
    };
    const login = vi.fn().mockResolvedValue(challenge);
    const verifyMfa = vi.fn().mockResolvedValue({
      ...testUser,
      mfa_enabled: true,
    });
    const client = createTestClient({
      getCurrentUser: async () => {
        throw new ApiError(401, "Session absente ou expirée.");
      },
      login,
      verifyMfa,
    });

    render(<App client={client} />);

    await user.type(
      await screen.findByLabelText("Adresse email"),
      "investor@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(
      await screen.findByRole("heading", {
        name: "Vérification en deux étapes",
      }),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Code de vérification"), "123456");
    await user.click(screen.getByRole("button", { name: "Continuer" }));

    expect(verifyMfa).toHaveBeenCalledWith("challenge-token", "123456");
    expect(
      await screen.findByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    const user = userEvent.setup();
    const logout = vi.fn().mockResolvedValue(undefined);

    render(<App client={createTestClient({ logout })} />);

    await user.click(
      await screen.findByRole("button", { name: "Se déconnecter" }),
    );
    expect(logout).toHaveBeenCalledOnce();
    expect(
      await screen.findByRole("heading", { name: "Se connecter" }),
    ).toBeInTheDocument();
  });

  it("keeps the session visible when server-side logout fails", async () => {
    const user = userEvent.setup();
    const logout = vi
      .fn()
      .mockRejectedValue(new ApiError(503, "Service indisponible."));

    render(<App client={createTestClient({ logout })} />);

    await user.click(
      await screen.findByRole("button", { name: "Se déconnecter" }),
    );

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent(
      "La déconnexion a échoué. Votre session est encore active.",
    );
    expect(
      screen.getByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Se connecter" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Se déconnecter" }));
    expect(logout).toHaveBeenCalledTimes(2);
  });

  it("prevents concurrent logout requests", async () => {
    const user = userEvent.setup();
    let completeLogout: (() => void) | undefined;
    const logout = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          completeLogout = resolve;
        }),
    );

    render(<App client={createTestClient({ logout })} />);

    await user.click(
      await screen.findByRole("button", { name: "Se déconnecter" }),
    );

    const pendingButton = screen.getByRole("button", { name: "Déconnexion…" });
    expect(pendingButton).toBeDisabled();
    expect(logout).toHaveBeenCalledOnce();

    await act(async () => completeLogout?.());
    expect(
      await screen.findByRole("heading", { name: "Se connecter" }),
    ).toBeInTheDocument();
  });

  it("returns to login when a business request reports an expired session", async () => {
    let expire: () => void = () => undefined;
    const client = createTestClient({
      onUnauthorized: (handler) => {
        expire = handler;
        return () => undefined;
      },
    });

    render(<App client={client} />);

    expect(await screen.findByText("investor@example.com")).toBeInTheDocument();

    act(() => expire());

    expect(
      await screen.findByText(
        "Votre session a expiré. Connectez-vous de nouveau.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Vue d’ensemble")).not.toBeInTheDocument();
  });

  it("updates a company from the investment universe", async () => {
    const user = userEvent.setup();
    const updateCompany = vi.fn().mockResolvedValue({
      id: "company-1",
      name: "Air Liquide SA",
      ticker: "AI.PA",
      exchange: "Euronext Paris",
      country: "France",
      currency: "EUR",
      status: "pending",
    });
    render(
      <App
        client={createTestClient({
          listCompanies: async () => [
            {
              id: "company-1",
              name: "Air Liquide",
              ticker: "AI.PA",
              exchange: "Euronext Paris",
              country: "France",
              currency: "EUR",
              status: "pending",
            },
          ],
          updateCompany,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Modifier ou retirer Air Liquide" }),
    );
    const name = screen.getByLabelText("Nom de l’entreprise");
    await user.clear(name);
    await user.type(name, "Air Liquide SA");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(updateCompany).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ name: "Air Liquide SA" }),
    );
    expect(await screen.findByText("Air Liquide SA")).toBeInTheDocument();
  });

  it("deletes a Greek company with an inline confirmation", async () => {
    const user = userEvent.setup();
    const deleteCompany = vi.fn().mockResolvedValue(undefined);
    render(
      <App
        client={createTestClient({
          listCompanies: async () => [
            {
              id: "company-greek",
              name: "ALPHA SERVICES AND HOLDINGS",
              ticker: "ALPHA.AT",
              exchange: "Euronext Athens",
              country: "Grèce",
              currency: "EUR",
              status: "pending",
              index_memberships: ["ATHEXCOMP"],
            },
          ],
          deleteCompany,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Modifier ou retirer ALPHA SERVICES AND HOLDINGS",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Supprimer définitivement" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Confirmer la suppression définitive de ALPHA SERVICES AND HOLDINGS",
    );
    await user.click(
      screen.getByRole("button", { name: "Confirmer la suppression" }),
    );

    expect(deleteCompany).toHaveBeenCalledWith("company-greek");
    expect(
      screen.queryByText("ALPHA SERVICES AND HOLDINGS"),
    ).not.toBeInTheDocument();
  });

  it("selects and deletes every company displayed in the investment universe", async () => {
    const user = userEvent.setup();
    const companies = [
      {
        id: "company-air-liquide",
        name: "Air Liquide",
        ticker: "AI.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "pending" as const,
      },
      {
        id: "company-sanofi",
        name: "Sanofi",
        ticker: "SAN.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "pending" as const,
      },
      {
        id: "company-favorite",
        name: "L'Oréal",
        ticker: "OR.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "ready" as const,
        is_favorite: true,
      },
    ];
    const deleteCompanies = vi.fn().mockResolvedValue({
      deleted_ids: ["company-air-liquide", "company-sanofi"],
    });
    render(
      <App
        client={createTestClient({
          listCompanies: async () => companies,
          deleteCompanies,
        })}
      />,
    );

    const universe = await screen.findByRole("region", {
      name: "Univers d’investissement",
    });
    await user.click(
      within(universe).getByRole("checkbox", {
        name: "Sélectionner toutes les valeurs affichées",
      }),
    );

    expect(within(universe).getByText("2 valeurs sélectionnées")).toBeInTheDocument();
    await user.click(
      within(universe).getByRole("button", { name: "Supprimer la sélection" }),
    );
    expect(within(universe).getByRole("alert")).toHaveTextContent(
      "Supprimer définitivement 2 valeurs",
    );
    expect(deleteCompanies).not.toHaveBeenCalled();

    await user.click(
      within(universe).getByRole("button", {
        name: "Confirmer la suppression groupée",
      }),
    );

    expect(deleteCompanies).toHaveBeenCalledWith([
      "company-air-liquide",
      "company-sanofi",
    ]);
    expect(within(universe).queryByText("Air Liquide")).not.toBeInTheDocument();
    expect(within(universe).queryByText("Sanofi")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Favoris" })).toHaveTextContent("L'Oréal");
  });

  it("keeps a scored company in the persistent favorites space", async () => {
    const user = userEvent.setup();
    const company = {
      id: "company-favorite",
      name: "AEGEAN AIRLINES",
      ticker: "AEGN.AT",
      exchange: "Euronext Athens",
      country: "Grèce",
      currency: "EUR",
      status: "ready" as const,
      latest_mk_score: 70,
      is_favorite: false,
    };
    const updateCompany = vi.fn().mockImplementation(async (_id, payload) => ({
      ...company,
      ...payload,
    }));
    render(
      <App
        client={createTestClient({
          listCompanies: async () => [company],
          updateCompany,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Ajouter AEGEAN AIRLINES aux favoris",
      }),
    );

    expect(updateCompany).toHaveBeenCalledWith("company-favorite", {
      is_favorite: true,
    });
    const universe = screen.getByRole("region", {
      name: "Univers d’investissement",
    });
    const favorites = screen.getByRole("region", { name: "Favoris" });
    expect(
      within(universe).queryByText("AEGEAN AIRLINES"),
    ).not.toBeInTheDocument();
    expect(within(favorites).getByText("AEGEAN AIRLINES")).toBeInTheDocument();
    expect(
      within(favorites).getByRole("button", {
        name: "Retirer AEGEAN AIRLINES des favoris",
      }),
    ).toBeInTheDocument();
  });

  it("allows a financial institution without an MK Score to become a favorite", async () => {
    const user = userEvent.setup();
    const bank = {
      id: "company-bank",
      name: "ALPHA BANK",
      ticker: "ALPHA.AT",
      exchange: "Euronext Athens",
      country: "Grèce",
      currency: "EUR",
      status: "ready" as const,
      latest_mk_score: null,
      is_favorite: false,
    };
    const updateCompany = vi.fn().mockImplementation(async (_id, payload) => ({
      ...bank,
      ...payload,
    }));
    render(
      <App
        client={createTestClient({
          listCompanies: async () => [bank],
          updateCompany,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Ajouter ALPHA BANK aux favoris",
      }),
    );

    expect(updateCompany).toHaveBeenCalledWith("company-bank", {
      is_favorite: true,
    });
    const universe = screen.getByRole("region", {
      name: "Univers d’investissement",
    });
    const favorites = screen.getByRole("region", { name: "Favoris" });
    expect(within(universe).queryByText("ALPHA BANK")).not.toBeInTheDocument();
    expect(within(favorites).getByText("ALPHA BANK")).toBeInTheDocument();
    expect(within(favorites).getByText("—")).toBeInTheDocument();
  });

  it("adds selected CAC Next 20 constituents without entering a ticker", async () => {
    const user = userEvent.setup();
    const addIndexCompanies = vi.fn().mockResolvedValue({
      created: [
        {
          id: "company-abivax",
          name: "ABIVAX",
          ticker: "ABVX.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending",
          isin: "FR0012333284",
          index_memberships: ["CACNEXT20"],
        },
      ],
      existing: [],
      errors: [],
    });
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "CACNEXT20",
              name: "CAC Next 20",
              isin: "QS0010989109",
              market: "XPAR",
              provider: "Euronext",
            },
          ],
          getIndex: async () => ({
            code: "CACNEXT20",
            name: "CAC Next 20",
            isin: "QS0010989109",
            market: "XPAR",
            provider: "Euronext",
            as_of: "31/07/2026",
            source_url: "https://live.euronext.com/example",
            constituents: [
              {
                name: "ABIVAX",
                isin: "FR0012333284",
                mic: "XPAR",
                trading_location: "Euronext Paris",
                country: "France",
              },
            ],
          }),
          addIndexCompanies,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );
    await user.click(await screen.findByRole("checkbox", { name: /ABIVAX/ }));
    await user.click(
      screen.getByRole("button", { name: "Ajouter 1 à l’univers" }),
    );

    expect(addIndexCompanies).toHaveBeenCalledWith([
      expect.objectContaining({ name: "ABIVAX", index_code: "CACNEXT20" }),
    ]);
    expect(await screen.findByText("ABVX.PA")).toBeInTheDocument();
  });

  it("groups United States indices under the America zone", async () => {
    const user = userEvent.setup();
    const addIndexCompanies = vi.fn().mockResolvedValue({
      created: [
        {
          id: "company-apple",
          name: "Apple Inc.",
          ticker: "AAPL",
          exchange: "Nasdaq",
          country: "États-Unis",
          currency: "USD",
          status: "pending",
          index_memberships: ["NASDAQ100"],
        },
      ],
      existing: [],
      errors: [],
    });
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "NASDAQ100",
              name: "Nasdaq-100",
              isin: null,
              market: "XNAS",
              provider: "Nasdaq",
              region: "Amérique",
              country: "États-Unis",
            },
          ],
          getIndex: async () => ({
            code: "NASDAQ100",
            name: "Nasdaq-100",
            isin: null,
            market: "XNAS",
            provider: "Nasdaq",
            region: "Amérique",
            country: "États-Unis",
            as_of: "Aug 4, 2026",
            source_url: "https://api.nasdaq.com/example",
            constituents: [
              {
                name: "Apple Inc.",
                ticker: "AAPL",
                mic: "XNAS",
                trading_location: "Nasdaq",
                country: "États-Unis",
                currency: "USD",
              },
            ],
          }),
          addIndexCompanies,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );
    expect(
      await screen.findByRole("region", { name: "Indices Amérique" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /États-Unis.*1 indice général.*0 indice sectoriel/,
      }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("tablist", { name: "Indices généraux États-Unis" }),
    ).toBeInTheDocument();
    await user.click(await screen.findByRole("checkbox", { name: /Apple Inc./ }));
    await user.click(
      screen.getByRole("button", { name: "Ajouter 1 à l’univers" }),
    );

    expect(addIndexCompanies).toHaveBeenCalledWith([
      expect.objectContaining({
        ticker: "AAPL",
        currency: "USD",
        index_code: "NASDAQ100",
      }),
    ]);
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
  });

  it("shows sector indices inside their geographic region", async () => {
    const user = userEvent.setup();
    const getIndex = vi.fn().mockImplementation(async (code: string) => ({
      code,
      name: code === "EUROPEHEALTH" ? "STOXX Europe 600 Health Care" : "CAC 40",
      isin: null,
      market: code === "EUROPEHEALTH" ? "XETR" : "XPAR",
      provider: code === "EUROPEHEALTH" ? "iShares" : "Euronext",
      region: "Europe",
      country: code === "EUROPEHEALTH" ? "Europe" : "France",
      kind: code === "EUROPEHEALTH" ? "sector" as const : "broad" as const,
      sector: code === "EUROPEHEALTH" ? "Health Care" : null,
      as_of: "13/Aug/2026",
      source_url: "https://example.test",
      constituents: code === "EUROPEHEALTH"
        ? [{
            name: "Novo Nordisk",
            ticker: "NOVO-B.CO",
            isin: "DK0062498333",
            mic: "XCSE",
            trading_location: "Nasdaq Copenhagen",
            country: "Danemark",
            currency: "DKK",
          }]
        : [{
            name: "Air Liquide",
            ticker: "AI.PA",
            isin: "FR0000120073",
            mic: "XPAR",
            trading_location: "Euronext Paris",
            country: "France",
            currency: "EUR",
          }],
    }));
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "CAC40",
              name: "CAC 40",
              isin: null,
              market: "XPAR",
              provider: "Euronext",
              region: "Europe",
              country: "France",
              kind: "broad",
              sector: null,
            },
            {
              code: "EUROPEHEALTH",
              name: "STOXX Europe 600 Health Care",
              isin: null,
              market: "XETR",
              provider: "iShares",
              region: "Europe",
              country: "Europe",
              kind: "sector",
              sector: "Health Care",
            },
          ],
          getIndex,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );
    const sectorToggle = screen.getByRole("button", {
      name: /Indices sectoriels régionaux.*1 indice.*Europe/,
    });
    const franceToggle = screen.getByRole("button", {
      name: /France.*1 indice général.*0 indice sectoriel/,
    });
    expect(sectorToggle).toHaveAttribute("aria-expanded", "true");
    expect(franceToggle).toHaveAttribute("aria-expanded", "true");
    expect(
      Boolean(
        sectorToggle.compareDocumentPosition(franceToggle)
        & Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    ).toBe(true);
    expect(
      screen.getByRole("tablist", { name: "Indices généraux France" }),
    ).toBeInTheDocument();

    await user.click(franceToggle);
    expect(
      screen.getByRole("tablist", { name: "Indices sectoriels régionaux Europe" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("tablist", { name: "Indices généraux France" }),
    ).not.toBeInTheDocument();

    await user.click(franceToggle);
    expect(
      screen.getByRole("tablist", { name: "Indices généraux France" }),
    ).toBeInTheDocument();
    const sectorTabs = screen.getByRole("tablist", {
      name: "Indices sectoriels régionaux Europe",
    });
    await user.click(
      within(sectorTabs).getByRole("tab", {
        name: /Santé.*STOXX Europe 600 Health Care/,
      }),
    );

    expect(sectorToggle).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("tablist", { name: "Indices sectoriels régionaux Europe" }),
    ).toBeInTheDocument();
    expect(getIndex).toHaveBeenLastCalledWith("EUROPEHEALTH");
    expect(
      await screen.findByRole("checkbox", { name: /Novo Nordisk/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/secteur Santé/)).toBeInTheDocument();
  });

  it("groups China and its CSI indices under the Asia zone", async () => {
    const user = userEvent.setup();
    const getIndex = vi.fn().mockImplementation(async (code: string) => ({
      code,
      name: code === "CNTECH" ? "CSI 300 Information Technology" : "CAC 40",
      isin: null,
      market: code === "CNTECH" ? "XSHG" : "XPAR",
      provider: code === "CNTECH" ? "CSI (via iShares)" : "Euronext",
      region: code === "CNTECH" ? "Asie" : "Europe",
      country: code === "CNTECH" ? "Chine" : "France",
      kind: code === "CNTECH" ? "sector" as const : "broad" as const,
      sector: code === "CNTECH" ? "Information Technology" : null,
      as_of: "14-Aug-2026",
      source_url: "https://example.test",
      constituents: code === "CNTECH"
        ? [{
            name: "Zhongji Innolight",
            ticker: "300308",
            isin: null,
            mic: "XSHE",
            trading_location: "Shenzhen Stock Exchange",
            country: "China",
            currency: "CNY",
          }]
        : [],
    }));
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "CAC40",
              name: "CAC 40",
              isin: null,
              market: "XPAR",
              provider: "Euronext",
              region: "Europe",
              country: "France",
              kind: "broad",
              sector: null,
            },
            {
              code: "CSI300",
              name: "CSI 300",
              isin: null,
              market: "XSHG",
              provider: "CSI (via iShares)",
              region: "Asie",
              country: "Chine",
              kind: "broad",
              sector: null,
            },
            {
              code: "CNTECH",
              name: "CSI 300 Information Technology",
              isin: null,
              market: "XSHG",
              provider: "CSI (via iShares)",
              region: "Asie",
              country: "Chine",
              kind: "sector",
              sector: "Information Technology",
            },
          ],
          getIndex,
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );
    await user.click(screen.getByRole("button", { name: "Asie" }));

    expect(
      screen.getByRole("region", { name: "Indices Asie" }),
    ).toBeInTheDocument();

    const chinaToggle = screen.getByRole("button", {
      name: /Chine.*1 indice général.*1 indice sectoriel/,
    });
    expect(chinaToggle).toHaveAttribute("aria-expanded", "true");
    const chinaSectors = screen.getByRole("tablist", {
      name: "Indices sectoriels Chine",
    });
    await user.click(
      within(chinaSectors).getByRole("tab", {
        name: /Technologies de l’information.*CSI 300 Information Technology/,
      }),
    );
    expect(getIndex).toHaveBeenLastCalledWith("CNTECH");
    expect(chinaToggle).toHaveAttribute("aria-expanded", "true");
    expect(
      await screen.findByRole("checkbox", { name: /Zhongji Innolight/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Diversification limitée/)).toBeInTheDocument();
  });

  it("groups the ATHEX Composite under Greece in Europe", async () => {
    const user = userEvent.setup();
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "ATHEXCOMP",
              name: "ATHEX Composite",
              isin: "GRI99117A004",
              market: "XATH",
              provider: "Euronext Athens",
              region: "Europe",
              country: "Grèce",
            },
          ],
          getIndex: async () => ({
            code: "ATHEXCOMP",
            name: "ATHEX Composite",
            isin: "GRI99117A004",
            market: "XATH",
            provider: "Euronext Athens",
            region: "Europe",
            country: "Grèce",
            as_of: "2026.08.07",
            source_url: "https://athens.euronext.com/example",
            constituents: [
              {
                name: "Coca-Cola HBC AG",
                ticker: "EEE.AT",
                mic: "XATH",
                trading_location: "Euronext Athens",
                country: "Grèce",
                currency: "EUR",
              },
            ],
          }),
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );

    expect(
      screen.getByRole("tablist", { name: "Indices généraux Grèce" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "ATHEX Composite" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      await screen.findByRole("checkbox", { name: /Coca-Cola HBC AG/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/EEE\.AT/)).toBeInTheDocument();
  });

  it("shows the selected index constituents and expands one zone at a time", async () => {
    const user = userEvent.setup();
    render(
      <App
        client={createTestClient({
          listIndices: async () => [
            {
              code: "CAC40",
              name: "CAC 40",
              isin: null,
              market: "XPAR",
              provider: "Euronext",
              region: "Europe",
              country: "France",
            },
            {
              code: "SP500",
              name: "S&P 500",
              isin: null,
              market: "XNYS",
              provider: "S&P Dow Jones Indices",
              region: "Amérique",
              country: "\u00c9tats-Unis",
            },
          ],
          getIndex: async (code) => ({
            code,
            name: code === "CAC40" ? "CAC 40" : "S&P 500",
            isin: null,
            market: code === "CAC40" ? "XPAR" : "XNYS",
            provider: "Test",
            as_of: "05/08/2026",
            source_url: "https://example.test",
            constituents: code === "CAC40"
              ? [{
                  name: "Airbus",
                  ticker: "AIR.PA",
                  mic: "XPAR",
                  trading_location: "Euronext Paris",
                  country: "France",
                }]
              : [{
                  name: "Apple Inc.",
                  ticker: "AAPL",
                  mic: "XNAS",
                  trading_location: "Nasdaq",
                  country: "\u00c9tats-Unis",
                }],
          }),
        })}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "Explorer les indices" }),
    );
    expect(await screen.findByRole("checkbox", { name: /Airbus/ })).toBeInTheDocument();

    const europe = screen.getByRole("button", { name: "Europe" });
    const america = screen.getByRole("button", { name: "Amérique" });
    await user.click(america);
    expect(europe).toHaveAttribute("aria-expanded", "false");
    expect(america).toHaveAttribute("aria-expanded", "true");

    await user.click(screen.getByRole("tab", { name: "S&P 500" }));
    expect(await screen.findByRole("checkbox", { name: /Apple Inc./ })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Airbus/ })).not.toBeInTheDocument();
  });
});

describe("MK-VIP dashboard", () => {
  it("shows the empty investment universe", async () => {
    render(<App client={createTestClient()} />);

    expect(
      await screen.findByRole("heading", { name: "Vue d’ensemble" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Aucune entreprise importée")).toBeInTheDocument();
    expect(screen.getByText("Import")).toBeInTheDocument();
    expect(screen.getByText("MK Score")).toBeInTheDocument();
    expect(
      screen.getByText("Version 0.12 Indices internationaux"),
    ).toBeInTheDocument();
  });

  it("connects every sidebar entry to a real section", async () => {
    const user = userEvent.setup();
    render(<App client={createTestClient()} />);

    const destinations = [
      ["Entreprises", "#companies"],
      ["Analyses", "#analyses"],
      ["Règles", "#rules"],
      ["Journal", "#journal"],
    ] as const;
    for (const [label, href] of destinations) {
      const link = await screen.findByRole("link", { name: label });
      expect(link).toHaveAttribute("href", href);
    }

    await user.click(screen.getByRole("link", { name: "Journal" }));
    expect(screen.getByRole("link", { name: "Journal" })).toHaveAttribute(
      "aria-current",
      "location",
    );
    expect(
      screen.getByRole("heading", { name: "Journal des analyses" }),
    ).toBeInTheDocument();
  });

  it("configures and disables MFA from the security drawer", async () => {
    const user = userEvent.setup();
    const setupMfa = vi.fn().mockResolvedValue({
      secret: "JBSWY3DPEHPK3PXP",
      otpauth_uri: "otpauth://totp/MK-VIP:investor@example.com",
      expires_at: "2026-07-26T10:10:00Z",
    });
    const confirmMfa = vi.fn().mockResolvedValue({
      recovery_codes: ["AAAAA-BBBBB", "CCCCC-DDDDD"],
    });
    const disableMfa = vi.fn().mockResolvedValue(undefined);
    const client = createTestClient({ setupMfa, confirmMfa, disableMfa });

    render(<App client={client} />);

    await user.click(await screen.findByRole("button", { name: "Sécurité" }));
    await user.click(
      screen.getByRole("button", { name: "Configurer le MFA" }),
    );
    expect(await screen.findByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Code de vérification"), "123456");
    await user.click(screen.getByRole("button", { name: "Activer le MFA" }));

    expect(confirmMfa).toHaveBeenCalledWith("123456");
    expect(await screen.findByText("AAAAA-BBBBB")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "J’ai enregistré mes codes" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Désactiver le MFA" }),
    );
    await user.type(screen.getByLabelText("Code de vérification"), "AAAAA-BBBBB");
    await user.click(
      screen.getByRole("button", { name: "Désactiver le MFA" }),
    );

    expect(disableMfa).toHaveBeenCalledWith("AAAAA-BBBBB");
    expect(
      await screen.findByRole("button", { name: "Configurer le MFA" }),
    ).toBeInTheDocument();
  });

  it("lists and revokes another active session", async () => {
    const user = userEvent.setup();
    const currentSession = {
      id: "session-current",
      created_at: "2026-07-26T10:00:00Z",
      last_seen_at: "2026-07-26T10:05:00Z",
      expires_at: "2026-08-25T10:00:00Z",
      user_agent: "Navigateur actuel",
      current: true,
    };
    const otherSession = {
      id: "session-other",
      created_at: "2026-07-25T08:00:00Z",
      last_seen_at: "2026-07-25T09:00:00Z",
      expires_at: "2026-08-24T08:00:00Z",
      user_agent: "Autre navigateur",
      current: false,
    };
    const listSessions = vi
      .fn()
      .mockResolvedValueOnce([currentSession, otherSession])
      .mockResolvedValueOnce([currentSession]);
    const revokeSession = vi.fn().mockResolvedValue(undefined);

    render(
      <App client={createTestClient({ listSessions, revokeSession })} />,
    );

    await user.click(await screen.findByRole("button", { name: "Sécurité" }));
    expect(await screen.findByText("Autre navigateur")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Révoquer" }));

    expect(revokeSession).toHaveBeenCalledWith("session-other");
    expect(screen.queryByText("Autre navigateur")).not.toBeInTheDocument();
  });

  it("uses index exploration instead of manual company import", async () => {
    const user = userEvent.setup();
    render(<App client={createTestClient()} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Choisir dans les indices",
      }),
    );

    expect(
      screen.getByRole("heading", { name: "Explorer un indice boursier" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Importer une entreprise" }),
    ).not.toBeInTheDocument();
  });

  it("opens the financial import for a pending company", async () => {
    const user = userEvent.setup();
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending",
        },
      ],
      createCompany: async (payload) => ({
        id: "company-2",
        status: "pending",
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Non utilisé dans ce scénario.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Importer les données financières pour Air Liquide",
      }),
    );

    expect(
      screen.getByRole("heading", {
        name: "Charger l’historique financier",
      }),
    ).toBeInTheDocument();
  });

  it("restores the latest MK score when companies are loaded", async () => {
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready",
          latest_mk_score: 72.5,
        },
      ],
      createCompany: async (payload) => ({
        id: "company-2",
        status: "pending",
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Non utilisé dans ce scénario.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });

    render(<App client={client} />);

    expect(await screen.findByText("MK Score 72.5")).toBeInTheDocument();
    expect(screen.getByLabelText("analyses : 1")).toBeInTheDocument();
  });

  it("imports the available public financial history automatically", async () => {
    const user = userEvent.setup();
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending" as const,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Le formulaire manuel ne doit pas être utilisé.");
      },
      importFinancialsAutomatically: async (companyId: string) => {
        if (companyId !== "company-1") {
          throw new Error("Mauvaise entreprise.");
        }
        const snapshot = {
          id: "analysis-1",
          company_id: companyId,
          fiscal_year: 2025,
          source: "Yahoo Finance · AI.PA · exercice 2025",
          currency: "EUR",
          revenue: 1000,
          ebitda: 450,
          depreciation_amortization: 20,
          ebit: 400,
          interest_expense: 40,
          operating_cash_flow: 300,
          capex: 40,
          net_income: 250,
          market_cap: 4500,
          total_assets: 4000,
          current_assets: 600,
          current_liabilities: 250,
          financial_debt: 600,
          cash: 100,
          total_equity: 1000,
          mk_score: 80,
          metrics: [],
          indicators: [],
          quality_score: 75,
          safety_score: 100,
          created_at: "2026-07-26T00:00:00Z",
        };
        return {
          company_id: companyId,
          snapshots: [snapshot],
          trend: {
            periods: 1,
            first_year: 2025,
            last_year: 2025,
            revenue_cagr: null,
            net_income_cagr: null,
            free_cash_flow_cagr: null,
          },
        };
      },
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Importer les données financières pour Air Liquide",
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "Charger l’historique",
      }),
    );

    expect(await screen.findByText("1 exercice disponible")).toBeInTheDocument();
  });

  it("opens the financial engine analysis for a ready company", async () => {
    const user = userEvent.setup();
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready" as const,
          latest_mk_score: 80,
          latest_quality_score: 75,
          latest_safety_score: 100,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 450,
            depreciation_amortization: 20,
            ebit: 400,
            interest_expense: 40,
            operating_cash_flow: 300,
            capex: 40,
            net_income: 250,
            market_cap: 4_500,
            total_assets: 4_000,
            current_assets: 600,
            current_liabilities: 250,
            financial_debt: 600,
            cash: 100,
            total_equity: 1_000,
            metrics: [],
            indicators: [
              {
                key: "free_cash_flow",
                label: "Free Cash Flow",
                value: 260,
                unit: "EUR",
                formula:
                  "Flux de trésorerie d’exploitation − investissements",
              },
              {
                key: "return_on_equity",
                label: "Rendement des capitaux propres (ROE)",
                value: 0.25,
                unit: "ratio",
                formula: "Résultat net / capitaux propres",
              },
            ],
            mk_score: 80,
            quality_score: 75,
            safety_score: 100,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Voir l’analyse financière de Air Liquide",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "Historique fondamental" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Fondamentaux du dernier exercice" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Historique annuel" })).toBeInTheDocument();
    expect(screen.getByText("Flux de trésorerie d’exploitation")).toBeInTheDocument();
    expect(screen.getAllByText("300 M EUR").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Historique insuffisant").length).toBeGreaterThan(0);
  });

  it("creates an explainable valuation from the latest analysis", async () => {
    const user = userEvent.setup();
    let submittedGrowthRate: number | undefined;
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready" as const,
          latest_mk_score: 80,
          latest_quality_score: 75,
          latest_safety_score: 100,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 300,
            depreciation_amortization: 40,
            ebit: 250,
            interest_expense: 20,
            operating_cash_flow: 180,
            capex: 80,
            net_income: 160,
            market_cap: 2_200,
            total_assets: 2_000,
            current_assets: 500,
            current_liabilities: 250,
            financial_debt: 400,
            cash: 100,
            total_equity: 800,
            metrics: [],
            indicators: [],
            mk_score: 80,
            quality_score: 75,
            safety_score: 100,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: async () => [],
      createValuation: async (
        companyId: string,
        payload: Parameters<CompanyClient["createValuation"]>[1],
      ) => {
        submittedGrowthRate = payload.assumptions.growth_rate;
        return {
          id: "valuation-1",
          company_id: companyId,
          financial_snapshot_id: "analysis-1",
          fiscal_year: payload.fiscal_year,
          currency: "EUR",
          market_cap: 2_200,
          assumptions: {
            growth_rate: 0.05,
            terminal_growth_rate: 0.02,
            cost_of_equity: 0.1,
            wacc: 0.08,
            tax_rate: 0.25,
            projection_years: 5,
            target_pe: 15,
            corporate_bond_yield: 0.044,
            margin_of_safety: 0.25,
          },
          methods: [
            {
              key: "dcf",
              label: "DCF des flux disponibles",
              value: 1_446.21,
              category: "proxy",
              formula: "Somme des FCF projetés actualisés",
              base_metric: "Free Cash Flow",
              note: "Proxy de flux aux actionnaires.",
            },
            {
              key: "buffett_owner_earnings",
              label: "Buffett Owner Earnings",
              value: 1_735.45,
              category: "proxy",
              formula: "Résultat net + amortissements − investissements",
              base_metric: "Owner Earnings",
              note: "Capex de maintenance approximé.",
            },
            {
              key: "earnings_power_value",
              label: "Earnings Power Value",
              value: 2_043.75,
              category: "intrinsic",
              formula: "NOPAT / WACC − dette + trésorerie",
              base_metric: "NOPAT",
              note: "Sans croissance future.",
            },
            {
              key: "graham",
              label: "Formule de Graham",
              value: 2_960,
              category: "proxy",
              formula: "Résultat net × (8,5 + 2g) × 4,4 / Y",
              base_metric: "Résultat net",
              note: "Raccourci historique.",
            },
            {
              key: "pe_multiple",
              label: "Multiple de résultat",
              value: 2_400,
              category: "relative",
              formula: "Résultat net × PER cible",
              base_metric: "Résultat net",
              note: "Prix relatif.",
            },
          ],
          central_estimate: 2_043.75,
          margin_of_safety_value: 1_532.81,
          market_gap: -0.071023,
          created_at: "2026-07-26T00:00:00Z",
        };
      },
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Voir l’analyse financière de Air Liquide",
      }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Préparer une valorisation",
      }),
    );
    expect(
      screen.getByRole("heading", { name: "Hypothèses de valorisation" }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Estimer la valeur" }),
    );

    expect(submittedGrowthRate).toBe(0.05);
    expect(
      within(
        await screen.findByRole("article", {
          name: "Estimation centrale",
        }),
      ).getByText("2 043,75 M EUR"),
    ).toBeInTheDocument();
    expect(screen.getByText("DCF des flux disponibles")).toBeInTheDocument();
    expect(screen.getByText("Buffett Owner Earnings")).toBeInTheDocument();
    expect(screen.getByText("Earnings Power Value")).toBeInTheDocument();
    expect(screen.getByText("Formule de Graham")).toBeInTheDocument();
    expect(screen.getByText("Multiple de résultat")).toBeInTheDocument();
  });

  it("creates an explainable global score from the latest valuation", async () => {
    const user = userEvent.setup();
    let submittedValuationId: string | undefined;
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready" as const,
          latest_mk_score: 80,
          latest_quality_score: 50,
          latest_safety_score: 75,
        },
      ],
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-2",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 300,
            depreciation_amortization: 40,
            ebit: 250,
            interest_expense: 20,
            operating_cash_flow: 180,
            capex: 80,
            net_income: 160,
            market_cap: 2_200,
            total_assets: 2_000,
            current_assets: 500,
            current_liabilities: 250,
            financial_debt: 400,
            cash: 100,
            total_equity: 800,
            metrics: [],
            indicators: [],
            mk_score: 80,
            quality_score: 50,
            safety_score: 75,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: async (companyId: string) => [
        {
          id: "valuation-1",
          company_id: companyId,
          financial_snapshot_id: "analysis-1",
          fiscal_year: 2025,
          currency: "EUR",
          market_cap: 2_200,
          assumptions: {
            growth_rate: 0.05,
            terminal_growth_rate: 0.02,
            cost_of_equity: 0.1,
            wacc: 0.08,
            tax_rate: 0.25,
            projection_years: 5,
            target_pe: 15,
            corporate_bond_yield: 0.044,
            margin_of_safety: 0.25,
          },
          methods: [],
          central_estimate: 2_505.47,
          margin_of_safety_value: 1_879.1,
          market_gap: 0.13885,
          created_at: "2026-07-26T00:00:00Z",
        },
      ],
      createValuation: unusedCreateValuation,
      listScores: async () => [],
      createScore: async (
        companyId: string,
        payload: Parameters<CompanyClient["createScore"]>[1],
      ) => {
        submittedValuationId = payload.valuation_id;
        return {
          id: "score-1",
          company_id: companyId,
          financial_snapshot_id: "analysis-1",
          valuation_analysis_id: payload.valuation_id,
          fiscal_year: payload.fiscal_year,
          components: [
            {
              key: "quality",
              label: "MK Quality Score",
              score: 50,
              weight: 0.25,
              contribution: 12.5,
              formula: "Score qualité × 25 %",
              note: "Qualité opérationnelle.",
            },
            {
              key: "safety",
              label: "MK Safety Score",
              score: 75,
              weight: 0.25,
              contribution: 18.75,
              formula: "Score sécurité × 25 %",
              note: "Solidité financière.",
            },
            {
              key: "value",
              label: "MK Value Score",
              score: 77.77,
              weight: 0.25,
              contribution: 19.44,
              formula: "Écart à la valeur centrale",
              note: "Valorisation relative.",
            },
            {
              key: "moat",
              label: "MK Moat Score",
              score: 50,
              weight: 0.25,
              contribution: 12.5,
              formula: "Signaux favorables / 4",
              note: "Proxy quantitatif.",
            },
          ],
          insights: [
            {
              key: "quality",
              tone: "neutral" as const,
              label: "Qualité : 50/100.",
            },
            {
              key: "safety",
              tone: "positive" as const,
              label: "Sécurité : 75/100.",
            },
            {
              key: "value",
              tone: "positive" as const,
              label: "Valorisation : décote de 13,9 %.",
            },
            {
              key: "moat",
              tone: "neutral" as const,
              label: "Moat proxy : 2/4 signaux favorables.",
            },
          ],
          global_score: 63.19,
          signal: "watch" as const,
          signal_label: "À approfondir",
          created_at: "2026-07-26T00:00:00Z",
        };
      },
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Voir l’analyse financière de Air Liquide",
      }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Calculer le scoring global",
      }),
    );

    expect(submittedValuationId).toBe("valuation-1");
    expect(await screen.findByText("63,19")).toBeInTheDocument();
    expect(screen.getByText("À approfondir")).toBeInTheDocument();
    expect(screen.getAllByText("MK Quality Score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("MK Safety Score").length).toBeGreaterThan(0);
    expect(screen.getByText("MK Value Score")).toBeInTheDocument();
    expect(screen.getByText("MK Moat Score")).toBeInTheDocument();
    expect(
      screen.getByText("Moat proxy : 2/4 signaux favorables."),
    ).toBeInTheDocument();
  });

  it("shows and filters the decision dashboard before opening an analysis", async () => {
    const user = userEvent.setup();
    const companies = [
      {
        id: "company-1",
        name: "Air Liquide",
        ticker: "AI.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "ready" as const,
        latest_mk_score: 80,
        latest_quality_score: 50,
        latest_safety_score: 75,
      },
      {
        id: "company-2",
        name: "L'Oréal",
        ticker: "OR.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "ready" as const,
        latest_mk_score: 90,
        latest_quality_score: 100,
        latest_safety_score: 100,
      },
      {
        id: "company-3",
        name: "Danone",
        ticker: "BN.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "pending" as const,
      },
    ];
    const client = createTestClient({
      listCompanies: async () => companies,
      getDashboard: async () => ({
        summary: {
          companies: 3,
          ready: 2,
          scored: 2,
          favorable: 1,
          watch: 0,
          caution: 1,
          unscored: 1,
        },
        distribution: [
          {
            signal: "favorable" as const,
            label: "Profils favorables",
            count: 1,
          },
          {
            signal: "watch" as const,
            label: "À approfondir",
            count: 0,
          },
          {
            signal: "caution" as const,
            label: "Prudence",
            count: 1,
          },
          {
            signal: "unscored" as const,
            label: "Non scorées",
            count: 1,
          },
        ],
        companies: [
          {
            company_id: "company-2",
            name: "L'Oréal",
            ticker: "OR.PA",
            exchange: "Euronext Paris",
            country: "France",
            status: "ready" as const,
            fiscal_year: 2025,
            global_score: 88,
            signal: "favorable" as const,
            signal_label: "Profil favorable",
            market_gap: 0.19,
            weakest_component: {
              key: "moat",
              label: "MK Moat Score",
              score: 75,
            },
            updated_at: "2026-07-26T00:00:00Z",
          },
          {
            company_id: "company-1",
            name: "Air Liquide",
            ticker: "AI.PA",
            exchange: "Euronext Paris",
            country: "France",
            status: "ready" as const,
            fiscal_year: 2025,
            global_score: 48,
            signal: "caution" as const,
            signal_label: "Prudence",
            market_gap: -0.11,
            weakest_component: {
              key: "value",
              label: "MK Value Score",
              score: 28,
            },
            updated_at: "2026-07-26T00:00:00Z",
          },
          {
            company_id: "company-3",
            name: "Danone",
            ticker: "BN.PA",
            exchange: "Euronext Paris",
            country: "France",
            status: "pending" as const,
            fiscal_year: null,
            global_score: null,
            signal: "unscored" as const,
            signal_label: "À scorer",
            market_gap: null,
            weakest_component: null,
            updated_at: null,
          },
        ],
      }),
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-4",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: async (companyId: string) => ({
        company_id: companyId,
        snapshots: [
          {
            id: "analysis-1",
            company_id: companyId,
            fiscal_year: 2025,
            source: "Rapport annuel 2025",
            currency: "EUR",
            revenue: 1_000,
            ebitda: 300,
            depreciation_amortization: 40,
            ebit: 250,
            interest_expense: 20,
            operating_cash_flow: 180,
            capex: 80,
            net_income: 160,
            market_cap: 2_200,
            total_assets: 2_000,
            current_assets: 500,
            current_liabilities: 250,
            financial_debt: 400,
            cash: 100,
            total_equity: 800,
            metrics: [],
            indicators: [],
            mk_score: 80,
            quality_score: 50,
            safety_score: 75,
            created_at: "2026-07-26T00:00:00Z",
          },
        ],
        trend: {
          periods: 1,
          first_year: 2025,
          last_year: 2025,
          revenue_cagr: null,
          net_income_cagr: null,
          free_cash_flow_cagr: null,
        },
      }),
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);

    expect(
      await screen.findByRole("heading", { name: "Tableau de décision" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("profils favorables : 1"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Distribution des signaux" }),
    ).toBeInTheDocument();

    const portfolio = screen.getByRole("region", {
      name: "Portefeuille de recherche",
    });
    expect(within(portfolio).getByText("88")).toBeInTheDocument();
    expect(within(portfolio).getByText("48")).toBeInTheDocument();
    expect(within(portfolio).getByText("MK Value Score")).toBeInTheDocument();

    await user.selectOptions(
      screen.getByRole("combobox", {
        name: "Filtrer le portefeuille de recherche",
      }),
      "caution",
    );
    expect(within(portfolio).queryByText("L'Oréal")).not.toBeInTheDocument();
    expect(within(portfolio).getByText("Air Liquide")).toBeInTheDocument();

    await user.click(
      within(portfolio).getByRole("button", {
        name: "Ouvrir l’analyse de Air Liquide",
      }),
    );
    expect(
      await screen.findByRole("dialog", { name: "Historique fondamental" }),
    ).toBeInTheDocument();
  });

  it("summarizes, compares and answers from the AI analyst drawer", async () => {
    const user = userEvent.setup();
    const requests: AIAnalysisPayload[] = [];
    const companies = [
      {
        id: "company-1",
        name: "Air Liquide",
        ticker: "AI.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "ready" as const,
      },
      {
        id: "company-2",
        name: "L'Oréal",
        ticker: "OR.PA",
        exchange: "Euronext Paris",
        country: "France",
        currency: "EUR",
        status: "ready" as const,
      },
    ];
    const client = createTestClient({
      listCompanies: async () => companies,
      createCompany: async (
        payload: Parameters<CompanyClient["createCompany"]>[0],
      ) => ({
        id: "company-3",
        status: "pending" as const,
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
      analyzeWithAI: async (payload: AIAnalysisPayload) => {
        requests.push(payload);
        return {
          mode: payload.mode,
          headline: "Lecture fondamentale synthétique",
          conclusion:
            "La qualité opérationnelle ressort mieux que la valorisation.",
          evidence: [
            {
              title: "Qualité des fondamentaux",
              finding:
                "Les données MK-VIP montrent une exploitation rentable.",
              source_ids: ["financial:analysis-1"],
            },
          ],
          risks: ["La marge de sécurité reste à confirmer."],
          missing_information: [
            "La trajectoire pluriannuelle n’est pas encore disponible.",
          ],
          sources: [
            {
              id: "financial:analysis-1",
              company_id: payload.company_id,
              kind: "financial" as const,
              label: "Air Liquide — analyse financière 2025",
              fiscal_year: 2025,
              created_at: "2026-07-26T00:00:00Z",
            },
          ],
          model: "test-analyst",
          generated_at: "2026-07-26T00:00:00Z",
          disclaimer:
            "Analyse informative fondée uniquement sur les données MK-VIP ; elle ne constitue pas un conseil en investissement.",
        };
      },
    });
    render(<App client={client} />);

    await user.click(
      await screen.findByRole("button", { name: "Interroger l’IA" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Analyste IA" }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Analyser avec l’IA" }),
    );
    expect(
      await screen.findByText(
        "La qualité opérationnelle ressort mieux que la valorisation.",
      ),
    ).toBeInTheDocument();
    expect(requests[0]).toEqual({
      mode: "summary",
      company_id: "company-1",
    });
    expect(
      screen.getByText("Air Liquide — analyse financière 2025"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Comparaison" }));
    await user.selectOptions(
      screen.getByLabelText("Entreprise de comparaison"),
      "company-2",
    );
    await user.click(
      screen.getByRole("button", { name: "Analyser avec l’IA" }),
    );
    expect(requests[1]).toEqual({
      mode: "comparison",
      company_id: "company-1",
      comparison_company_id: "company-2",
    });

    await user.click(screen.getByRole("button", { name: "Question" }));
    await user.type(
      screen.getByLabelText("Question à analyser"),
      "Quels sont les principaux risques ?",
    );
    await user.click(
      screen.getByRole("button", { name: "Analyser avec l’IA" }),
    );
    expect(requests[2]).toEqual({
      mode: "question",
      company_id: "company-1",
      question: "Quels sont les principaux risques ?",
    });
  });

  it("filters the investment universe by company name or ticker", async () => {
    const user = userEvent.setup();
    const client = createTestClient({
      listCompanies: async () => [
        {
          id: "company-1",
          name: "Air Liquide",
          ticker: "AI.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "ready",
        },
        {
          id: "company-2",
          name: "Danone",
          ticker: "BN.PA",
          exchange: "Euronext Paris",
          country: "France",
          currency: "EUR",
          status: "pending",
        },
      ],
      createCompany: async (payload) => ({
        id: "company-3",
        status: "pending",
        ...payload,
      }),
      importFinancials: async () => {
        throw new Error("Import manuel non utilisé.");
      },
      importFinancialsAutomatically: unusedAutomaticImport,
      getFinancialHistory: unusedFinancialHistory,
      listValuations: unusedValuations,
      createValuation: unusedCreateValuation,
      listScores: unusedScores,
      createScore: unusedCreateScore,
    });
    render(<App client={client} />);
    const universe = await screen.findByRole("region", {
      name: "Univers d’investissement",
    });

    await user.type(
      within(universe).getByPlaceholderText(
        "Rechercher une entreprise ou un ticker",
      ),
      "AI.PA",
    );

    expect(within(universe).getByText("Air Liquide")).toBeInTheDocument();
    expect(within(universe).queryByText("Danone")).not.toBeInTheDocument();
  });
});

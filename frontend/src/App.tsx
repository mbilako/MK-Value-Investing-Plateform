import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AuthCredentials,
  type CompanyClient,
  type LoginResult,
  type User,
} from "./api/client";
import { readAndClearAuthLink } from "./auth/link";
import { AuthScreen } from "./components/AuthScreen";
import { SessionLoading } from "./components/SessionLoading";
import { Workspace } from "./components/Workspace";

interface AppProps {
  client?: CompanyClient;
}

type AuthStatus = "checking" | "unauthenticated" | "authenticated";

export function App({ client = apiClient }: AppProps) {
  const [authLink, setAuthLink] = useState(() =>
    readAndClearAuthLink(window.location, window.history),
  );
  const [shouldRestoreSession] = useState(() => authLink === null);
  const [status, setStatus] = useState<AuthStatus>(
    shouldRestoreSession ? "checking" : "unauthenticated",
  );
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let expired = false;

    setStatus("checking");
    setUser(null);
    setNotice(null);

    const unsubscribe = client.onUnauthorized(() => {
      expired = true;
      setUser(null);
      setNotice("Votre session a expiré. Connectez-vous de nouveau.");
      setStatus("unauthenticated");
    });

    if (!shouldRestoreSession) {
      setStatus("unauthenticated");
      return unsubscribe;
    }

    client
      .getCurrentUser()
      .then((currentUser) => {
        if (!active || expired) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch((caughtError: unknown) => {
        if (!active || expired) return;
        setUser(null);
        if (!(caughtError instanceof ApiError && caughtError.status === 401)) {
          setNotice("Le service est momentanément indisponible.");
        }
        setStatus("unauthenticated");
      });

    return () => {
      active = false;
      unsubscribe();
    };
  }, [client, shouldRestoreSession]);

  const login = async (credentials: AuthCredentials): Promise<LoginResult> => {
    const result = await client.login(credentials);
    if (!("mfa_required" in result)) {
      setUser(result);
      setNotice(null);
      setStatus("authenticated");
    }
    return result;
  };

  const verifyMfa = async (challengeToken: string, code: string) => {
    const authenticatedUser = await client.verifyMfa(challengeToken, code);
    setUser(authenticatedUser);
    setNotice(null);
    setStatus("authenticated");
  };

  const logout = async () => {
    await client.logout();
    setUser(null);
    setNotice(null);
    setStatus("unauthenticated");
  };

  if (status === "checking") {
    return <SessionLoading />;
  }

  if (status === "authenticated" && user) {
    return (
      <Workspace
        client={client}
        user={user}
        onLogout={logout}
        onMfaStatusChange={(mfaEnabled) =>
          setUser((current) =>
            current ? { ...current, mfa_enabled: mfaEnabled } : current,
          )
        }
      />
    );
  }

  return (
    <AuthScreen
      notice={notice}
      authLink={authLink}
      onAuthLinkHandled={() => setAuthLink(null)}
      onLogin={login}
      onVerifyMfa={verifyMfa}
      onRegister={(credentials) => client.register(credentials)}
      onVerifyEmail={(token) => client.verifyEmail(token)}
      onResendVerification={(email) => client.resendVerification(email)}
      onRequestPasswordReset={(email) => client.requestPasswordReset(email)}
      onConfirmPasswordReset={(token, password) =>
        client.confirmPasswordReset(token, password)
      }
    />
  );
}

import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AuthCredentials,
  type CompanyClient,
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

  const authenticate = async (
    action: (credentials: AuthCredentials) => Promise<User>,
    credentials: AuthCredentials,
  ) => {
    const authenticatedUser = await action(credentials);
    setUser(authenticatedUser);
    setNotice(null);
    setStatus("authenticated");
  };

  const logout = async () => {
    try {
      await client.logout();
    } catch {
      // Local logout still succeeds when the remote session is unavailable.
    } finally {
      setUser(null);
      setNotice(null);
      setStatus("unauthenticated");
    }
  };

  if (status === "checking") {
    return <SessionLoading />;
  }

  if (status === "authenticated" && user) {
    return <Workspace client={client} user={user} onLogout={logout} />;
  }

  return (
    <AuthScreen
      notice={notice}
      authLink={authLink}
      onAuthLinkHandled={() => setAuthLink(null)}
      onLogin={(credentials) =>
        authenticate(client.login.bind(client), credentials)
      }
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

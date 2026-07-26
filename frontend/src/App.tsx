import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type AuthCredentials,
  type CompanyClient,
  type User,
} from "./api/client";
import { AuthScreen } from "./components/AuthScreen";
import { SessionLoading } from "./components/SessionLoading";
import { Workspace } from "./components/Workspace";

interface AppProps {
  client?: CompanyClient;
}

type AuthStatus = "checking" | "unauthenticated" | "authenticated";

export function App({ client = apiClient }: AppProps) {
  const [status, setStatus] = useState<AuthStatus>("checking");
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
  }, [client]);

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
      onLogin={(credentials) =>
        authenticate(client.login.bind(client), credentials)
      }
      onRegister={(credentials) =>
        authenticate(client.register.bind(client), credentials)
      }
    />
  );
}

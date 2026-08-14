import { useState } from "react";

import type { User } from "../api/client";

export interface UserMenuProps {
  user: User;
  onLogout(): Promise<void>;
  onOpenSecurity(): void;
}

export function UserMenu({ user, onLogout, onOpenSecurity }: UserMenuProps) {
  const [isLoggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  const logout = async () => {
    if (isLoggingOut) return;
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await onLogout();
    } catch {
      setLogoutError(
        "La déconnexion a échoué. Votre session est encore active. " +
          "Réessayez avant de quitter cet appareil.",
      );
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="user-menu-control">
      <div className="user-menu">
        <span className="user-menu__email">{user.email}</span>
        <button
          className="button button--text"
          type="button"
          onClick={onOpenSecurity}
          disabled={isLoggingOut}
        >
          Sécurité
        </button>
        <button
          className="button button--text"
          type="button"
          onClick={() => void logout()}
          disabled={isLoggingOut}
        >
          {isLoggingOut ? "Déconnexion…" : "Se déconnecter"}
        </button>
      </div>
      {logoutError && (
        <p className="user-menu__error" role="alert">
          {logoutError}
        </p>
      )}
    </div>
  );
}

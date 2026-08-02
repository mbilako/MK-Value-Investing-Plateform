import type { User } from "../api/client";

export interface UserMenuProps {
  user: User;
  onLogout(): Promise<void>;
  onOpenSecurity(): void;
}

export function UserMenu({ user, onLogout, onOpenSecurity }: UserMenuProps) {
  return (
    <div className="user-menu">
      <span className="user-menu__email">{user.email}</span>
      <button className="button button--text" type="button" onClick={onOpenSecurity}>
        Sécurité
      </button>
      <button
        className="button button--text"
        type="button"
        onClick={() => void onLogout()}
      >
        Se déconnecter
      </button>
    </div>
  );
}

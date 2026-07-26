import { useEffect, useRef, useState, type FormEvent } from "react";

import type { AuthCredentials } from "../api/client";

type AuthMode = "login" | "register";

export interface AuthScreenProps {
  notice?: string | null;
  onLogin(credentials: AuthCredentials): Promise<void>;
  onRegister(credentials: AuthCredentials): Promise<void>;
}

export function AuthScreen({
  notice = null,
  onLogin,
  onRegister,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);
  const visibleError = error ?? notice;

  useEffect(() => {
    if (error) {
      alertRef.current?.focus();
    }
  }, [error]);

  const selectMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setPassword("");
    setError(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const credentials = { email, password };

    try {
      if (mode === "register") {
        await onRegister(credentials);
      } else {
        await onLogin(credentials);
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La demande n’a pas pu aboutir.",
      );
    } finally {
      setBusy(false);
    }
  };

  const heading =
    mode === "register" ? "Créer votre compte" : "Se connecter";

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="auth-heading">
        <div className="auth-brand">
          <span className="brand__name">MK-VIP</span>
          <span className="brand__description">
            MK Value Investing Platform
          </span>
        </div>
        <div className="auth-card__intro">
          <p className="section-eyebrow">Espace investisseur personnel</p>
          <h1 id="auth-heading">{heading}</h1>
          <p>
            Retrouvez vos entreprises, analyses et décisions dans un espace
            privé.
          </p>
        </div>

        {visibleError ? (
          <p
            ref={alertRef}
            className="auth-error"
            role="alert"
            tabIndex={-1}
          >
            {visibleError}
          </p>
        ) : null}

        <form className="auth-form" onSubmit={submit}>
          <div className="field">
            <label htmlFor="auth-email">Adresse email</label>
            <input
              id="auth-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="auth-password">Mot de passe</label>
            <input
              id="auth-password"
              name="password"
              type="password"
              minLength={mode === "register" ? 12 : 1}
              maxLength={128}
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            {mode === "register" ? (
              <small>12 caractères minimum</small>
            ) : null}
          </div>
          <button
            className="button button--primary auth-submit"
            type="submit"
            disabled={busy}
          >
            {busy
              ? "Veuillez patienter…"
              : mode === "register"
                ? "Créer mon compte"
                : "Se connecter"}
          </button>
        </form>

        <div className="auth-mode">
          <span>
            {mode === "register"
              ? "Vous avez déjà un compte ?"
              : "Nouveau sur MK-VIP ?"}
          </span>
          <button
            className="button button--text"
            type="button"
            onClick={() =>
              selectMode(mode === "register" ? "login" : "register")
            }
          >
            {mode === "register" ? "Se connecter" : "Créer un compte"}
          </button>
        </div>
      </section>
    </main>
  );
}

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  ApiError,
  type AuthCredentials,
  type AuthMessage,
  type LoginResult,
  type MfaChallenge,
} from "../../api/client";

type AuthMode = "login" | "register";

interface AuthCredentialsFormProps {
  mode: AuthMode;
  notice: string | null;
  onLogin(credentials: AuthCredentials): Promise<LoginResult>;
  onMfaRequired(challenge: MfaChallenge): void;
  onRegister(credentials: AuthCredentials): Promise<AuthMessage>;
  onVerificationPending(email: string, message: string): void;
  onSelectMode(mode: AuthMode): void;
  onForgotPassword(): void;
  onResendVerification(email: string): Promise<AuthMessage>;
}

export function AuthCredentialsForm({
  mode,
  notice,
  onLogin,
  onMfaRequired,
  onRegister,
  onVerificationPending,
  onSelectMode,
  onForgotPassword,
  onResendVerification,
}: AuthCredentialsFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canResend, setCanResend] = useState(false);
  const alertRef = useRef<HTMLParagraphElement>(null);
  const visibleError = error ?? notice;

  useEffect(() => {
    if (visibleError) {
      alertRef.current?.focus();
    }
  }, [visibleError]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setCanResend(false);
    const credentials = { email, password };

    try {
      if (mode === "register") {
        const result = await onRegister(credentials);
        onVerificationPending(email, result.message);
      } else {
        const result = await onLogin(credentials);
        if ("mfa_required" in result) {
          onMfaRequired(result);
        }
      }
    } catch (caughtError) {
      setCanResend(
        mode === "login" &&
          caughtError instanceof ApiError &&
          caughtError.status === 403,
      );
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La demande n’a pas pu aboutir.",
      );
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setBusy(true);
    setError(null);

    try {
      const result = await onResendVerification(email);
      onVerificationPending(email, result.message);
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
    <>
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
            disabled={busy}
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
            disabled={busy}
            required
          />
          {mode === "register" ? <small>12 caractères minimum</small> : null}
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

      {mode === "login" ? (
        <div className="auth-actions">
          <button
            className="button button--text"
            type="button"
            onClick={onForgotPassword}
            disabled={busy}
          >
            Mot de passe oublié ?
          </button>
          {canResend ? (
            <button
              className="button button--text"
              type="button"
              onClick={resend}
              disabled={busy}
            >
              Renvoyer l’email de vérification
            </button>
          ) : null}
        </div>
      ) : null}

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
            onSelectMode(mode === "register" ? "login" : "register")
          }
          disabled={busy}
        >
          {mode === "register" ? "Se connecter" : "Créer un compte"}
        </button>
      </div>
    </>
  );
}

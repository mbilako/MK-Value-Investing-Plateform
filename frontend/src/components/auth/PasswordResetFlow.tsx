import { useEffect, useRef, useState, type FormEvent } from "react";

import type { AuthMessage } from "../../api/client";

type PasswordResetFlowProps =
  | {
      kind: "request";
      message: string | null;
      onRequest(email: string): Promise<AuthMessage>;
      onMessage(message: string): void;
      onBackToLogin(): void;
    }
  | {
      kind: "confirm";
      token: string;
      status: "form";
      onConfirm(token: string, password: string): Promise<void>;
      onSuccess(): void;
      onBackToLogin(): void;
    }
  | {
      kind: "confirm";
      status: "success";
      onBackToLogin(): void;
    };

export function PasswordResetFlow(props: PasswordResetFlowProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestResultRef = useRef<HTMLParagraphElement>(null);
  const confirmResultRef = useRef<HTMLHeadingElement>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);
  const requestMessage = props.kind === "request" ? props.message : null;
  const resetSucceeded =
    props.kind === "confirm" && props.status === "success";

  useEffect(() => {
    if (requestMessage) {
      requestResultRef.current?.focus();
    } else if (resetSucceeded) {
      confirmResultRef.current?.focus();
    }
  }, [requestMessage, resetSucceeded]);

  useEffect(() => {
    if (error) {
      alertRef.current?.focus();
    }
  }, [error]);

  const requestReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (props.kind !== "request") return;

    setBusy(true);
    setError(null);
    try {
      const result = await props.onRequest(email);
      props.onMessage(result.message);
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

  const confirmReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (props.kind !== "confirm" || props.status !== "form") return;

    setError(null);
    if (password !== confirmation) {
      setError("Les mots de passe doivent être identiques.");
      return;
    }

    setBusy(true);
    try {
      await props.onConfirm(props.token, password);
      props.onSuccess();
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

  if (props.kind === "request") {
    return (
      <div className="auth-result">
        <div className="auth-card__intro">
          <p className="section-eyebrow">Récupération du compte</p>
          <h1 id="auth-heading">Mot de passe oublié</h1>
          <p>
            Saisissez votre adresse email pour recevoir un lien de
            réinitialisation.
          </p>
        </div>

        {props.message ? (
          <p
            ref={requestResultRef}
            className="auth-success"
            aria-live="polite"
            tabIndex={-1}
          >
            {props.message}
          </p>
        ) : (
          <form className="auth-form" onSubmit={requestReset}>
            <div className="field">
              <label htmlFor="reset-email">Adresse email</label>
              <input
                id="reset-email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <button
              className="button button--primary auth-submit"
              type="submit"
              disabled={busy}
            >
              {busy ? "Veuillez patienter…" : "Envoyer le lien"}
            </button>
          </form>
        )}

        {error ? (
          <p
            ref={alertRef}
            className="auth-error"
            role="alert"
            tabIndex={-1}
          >
            {error}
          </p>
        ) : null}

        <button
          className="button button--text auth-back"
          type="button"
          onClick={props.onBackToLogin}
          disabled={busy}
        >
          Retour à la connexion
        </button>
      </div>
    );
  }

  if (props.status === "success") {
    return (
      <div className="auth-result">
        <div className="auth-card__intro">
          <p className="section-eyebrow">Récupération du compte</p>
          <h1
            id="auth-heading"
            ref={confirmResultRef}
            tabIndex={-1}
          >
            Mot de passe mis à jour
          </h1>
          <p className="auth-success" aria-live="polite">
            Votre nouveau mot de passe est enregistré. Connectez-vous pour
            continuer.
          </p>
        </div>
        <button
          className="button button--primary auth-submit"
          type="button"
          onClick={props.onBackToLogin}
        >
          Retour à la connexion
        </button>
      </div>
    );
  }

  return (
    <div className="auth-result">
      <div className="auth-card__intro">
        <p className="section-eyebrow">Récupération du compte</p>
        <h1 id="auth-heading">Choisir un nouveau mot de passe</h1>
        <p>Utilisez au moins 12 caractères, puis confirmez votre saisie.</p>
      </div>

      {error ? (
        <p
          ref={alertRef}
          className="auth-error"
          role="alert"
          tabIndex={-1}
        >
          {error}
        </p>
      ) : null}

      <form className="auth-form" onSubmit={confirmReset}>
        <div className="field">
          <label htmlFor="reset-password">Nouveau mot de passe</label>
          <input
            id="reset-password"
            name="password"
            type="password"
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="reset-password-confirmation">
            Confirmer le mot de passe
          </label>
          <input
            id="reset-password-confirmation"
            name="password-confirmation"
            type="password"
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
          />
        </div>
        <button
          className="button button--primary auth-submit"
          type="submit"
          disabled={busy}
        >
          {busy
            ? "Veuillez patienter…"
            : "Mettre à jour le mot de passe"}
        </button>
      </form>
    </div>
  );
}

import { useState, type FormEvent } from "react";

import type { MfaChallenge } from "../../api/client";

interface MfaChallengeFlowProps {
  challenge: MfaChallenge;
  onVerify(challengeToken: string, code: string): Promise<void>;
  onBackToLogin(): void;
}

export function MfaChallengeFlow({
  challenge,
  onVerify,
  onBackToLogin,
}: MfaChallengeFlowProps) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onVerify(challenge.challenge_token, code);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La vérification n’a pas pu aboutir.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-result">
      <div className="auth-card__intro">
        <p className="section-eyebrow">Sécurité du compte</p>
        <h1 id="auth-heading">Vérification en deux étapes</h1>
        <p>
          Saisissez le code de votre application d’authentification ou l’un de
          vos codes de récupération.
        </p>
      </div>
      {error ? <p className="auth-error" role="alert">{error}</p> : null}
      <form className="auth-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="mfa-code">Code de vérification</label>
          <input
            id="mfa-code"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            disabled={busy}
            required
          />
        </div>
        <button className="button button--primary auth-submit" disabled={busy}>
          {busy ? "Vérification…" : "Continuer"}
        </button>
      </form>
      <button
        className="button button--text auth-back"
        type="button"
        onClick={onBackToLogin}
        disabled={busy}
      >
        Retour à la connexion
      </button>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";

import type {
  AccountSession,
  CompanyClient,
  MfaSetup,
  User,
} from "../api/client";

interface SecurityDrawerProps {
  client: CompanyClient;
  user: User;
  onMfaStatusChange(mfaEnabled: boolean): void;
  onClose(): void;
}

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatSessionDate(value: string): string {
  return dateFormatter.format(new Date(value));
}

export function SecurityDrawer({
  client,
  user,
  onMfaStatusChange,
  onClose,
}: SecurityDrawerProps) {
  const [sessions, setSessions] = useState<AccountSession[]>([]);
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [isDisablingMfa, setDisablingMfa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await client.listSessions());
    } catch {
      setError("Les sessions actives n’ont pas pu être chargées.");
    }
  }, [client]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const beginSetup = async () => {
    setBusy(true);
    setError(null);
    try {
      setSetup(await client.setupMfa());
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La configuration a échoué.",
      );
    } finally {
      setBusy(false);
    }
  };

  const confirmSetup = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await client.confirmMfa(code);
      setRecoveryCodes(result.recovery_codes);
      setSetup(null);
      setCode("");
      onMfaStatusChange(true);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Le code est invalide.",
      );
    } finally {
      setBusy(false);
    }
  };

  const disableMfa = async () => {
    setBusy(true);
    setError(null);
    try {
      await client.disableMfa(code);
      setCode("");
      setDisablingMfa(false);
      onMfaStatusChange(false);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Le code est invalide.",
      );
    } finally {
      setBusy(false);
    }
  };

  const revokeOtherSessions = async () => {
    setBusy(true);
    setError(null);
    try {
      await client.revokeOtherSessions();
      await refreshSessions();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La révocation a échoué.",
      );
    } finally {
      setBusy(false);
    }
  };

  const revokeSession = async (sessionId: string) => {
    setBusy(true);
    setError(null);
    try {
      await client.revokeSession(sessionId);
      await refreshSessions();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "La révocation a échoué.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="drawer-layer" role="presentation">
      <button
        className="drawer-backdrop"
        type="button"
        onClick={onClose}
        aria-label="Fermer les paramètres de sécurité"
      />
      <aside
        className="drawer security-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="security-title"
      >
        <header className="drawer__head">
          <div>
            <p className="section-eyebrow">Compte personnel</p>
            <h2 id="security-title">Sécurité</h2>
          </div>
          <button className="button button--text" type="button" onClick={onClose}>
            Fermer
          </button>
        </header>
        <div className="security-drawer__body">
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <section className="security-section">
            <h3>Authentification à deux facteurs</h3>
            {recoveryCodes ? (
              <div className="security-recovery-codes">
                <p>
                  Conservez ces codes dans un endroit sûr. Ils ne seront plus
                  affichés.
                </p>
                <ul>
                  {recoveryCodes.map((recoveryCode) => (
                    <li key={recoveryCode}>{recoveryCode}</li>
                  ))}
                </ul>
                <button
                  className="button button--primary"
                  type="button"
                  onClick={() => setRecoveryCodes(null)}
                >
                  J’ai enregistré mes codes
                </button>
              </div>
            ) : setup ? (
              <div className="security-setup">
                <p>
                  Ajoutez le compte dans votre application avec cette clé, puis
                  saisissez son code à six chiffres.
                </p>
                <code>{setup.secret}</code>
                <a className="security-setup__link" href={setup.otpauth_uri}>
                  Ouvrir dans l’application d’authentification
                </a>
                <details>
                  <summary>Adresse de configuration</summary>
                  <code>{setup.otpauth_uri}</code>
                </details>
                <label htmlFor="security-mfa-code">Code de vérification</label>
                <input
                  id="security-mfa-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  disabled={busy}
                />
                <div className="security-actions">
                  <button
                    className="button button--primary"
                    type="button"
                    onClick={() => void confirmSetup()}
                    disabled={busy || code.length < 6}
                  >
                    Activer le MFA
                  </button>
                  <button
                    className="button button--text"
                    type="button"
                    onClick={() => {
                      setSetup(null);
                      setCode("");
                    }}
                    disabled={busy}
                  >
                    Annuler
                  </button>
                </div>
              </div>
            ) : user.mfa_enabled ? (
              isDisablingMfa ? (
                <div className="security-setup security-setup--danger">
                  <p>
                    Confirmez avec un code de votre application ou un code de
                    récupération. Les codes de récupération restants seront
                    supprimés.
                  </p>
                  <label htmlFor="security-disable-mfa-code">
                    Code de vérification
                  </label>
                  <input
                    id="security-disable-mfa-code"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    disabled={busy}
                  />
                  <div className="security-actions">
                    <button
                      className="button button--danger"
                      type="button"
                      onClick={() => void disableMfa()}
                      disabled={busy || code.length < 6}
                    >
                      Désactiver le MFA
                    </button>
                    <button
                      className="button button--text"
                      type="button"
                      onClick={() => {
                        setDisablingMfa(false);
                        setCode("");
                      }}
                      disabled={busy}
                    >
                      Annuler
                    </button>
                  </div>
                </div>
              ) : (
                <div className="security-status">
                  <p className="auth-success">
                    Le MFA est activé pour ce compte.
                  </p>
                  <button
                    className="button button--text"
                    type="button"
                    onClick={() => setDisablingMfa(true)}
                  >
                    Désactiver le MFA
                  </button>
                </div>
              )
            ) : (
              <>
                <p>
                  Protégez votre connexion avec une application
                  d’authentification et des codes de récupération.
                </p>
                <button
                  className="button button--primary"
                  type="button"
                  onClick={() => void beginSetup()}
                  disabled={busy}
                >
                  Configurer le MFA
                </button>
              </>
            )}
          </section>
          <section className="security-section">
            <div className="security-section__head">
              <h3>Sessions actives</h3>
              <button
                className="button button--text"
                type="button"
                onClick={() => void revokeOtherSessions()}
                disabled={busy || sessions.every((session) => session.current)}
              >
                Révoquer les autres
              </button>
            </div>
            {sessions.length === 0 ? (
              <p>Aucune session active n’a été trouvée.</p>
            ) : (
              <ul className="security-sessions">
                {sessions.map((session) => (
                  <li key={session.id}>
                    <div>
                      <strong>
                        {session.current ? "Cette session" : "Autre appareil"}
                      </strong>
                      <span>{session.user_agent ?? "Navigateur non identifié"}</span>
                      <span>
                        Activité : {formatSessionDate(session.last_seen_at)} ·
                        Expire : {formatSessionDate(session.expires_at)}
                      </span>
                    </div>
                    {!session.current ? (
                      <button
                        className="button button--text"
                        type="button"
                        onClick={() => void revokeSession(session.id)}
                        disabled={busy}
                      >
                        Révoquer
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}

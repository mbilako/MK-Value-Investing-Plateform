import { useEffect, useRef, useState } from "react";

import type { AuthMessage } from "../../api/client";

type VerificationFlowProps =
  | {
      kind: "pending";
      email: string;
      message: string;
      onResend(email: string): Promise<AuthMessage>;
      onMessage(message: string): void;
      onBackToLogin(): void;
    }
  | {
      kind: "result";
      token: string;
      status: "busy";
      onVerify(token: string): Promise<void>;
      onStatus(status: "success" | "error"): void;
      onBackToLogin(): void;
    }
  | {
      kind: "result";
      status: "success" | "error";
      onBackToLogin(): void;
    };

export function VerificationFlow(props: VerificationFlowProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const alertRef = useRef<HTMLParagraphElement>(null);
  const verificationRequestRef = useRef<Promise<void> | null>(null);
  const resultStatus = props.kind === "result" ? props.status : null;
  const busyVerification =
    props.kind === "result" && props.status === "busy" ? props : null;
  const verificationToken = busyVerification?.token ?? null;
  const verify = busyVerification?.onVerify ?? null;
  const setVerificationStatus =
    busyVerification?.onStatus ?? null;
  const pendingMessage = props.kind === "pending" ? props.message : null;

  useEffect(() => {
    if (
      resultStatus !== "busy" ||
      !verificationToken ||
      !verify ||
      !setVerificationStatus
    ) {
      return;
    }

    let active = true;
    const request =
      verificationRequestRef.current ??
      (verificationRequestRef.current = verify(verificationToken));

    request.then(
      () => {
        if (active) setVerificationStatus("success");
      },
      () => {
        if (active) setVerificationStatus("error");
      },
    );

    return () => {
      active = false;
    };
  }, [resultStatus, setVerificationStatus, verificationToken, verify]);

  useEffect(() => {
    if (
      props.kind === "pending" ||
      (resultStatus !== null && resultStatus !== "busy")
    ) {
      headingRef.current?.focus();
    }
  }, [pendingMessage, props.kind, resultStatus]);

  useEffect(() => {
    if (error) {
      alertRef.current?.focus();
    }
  }, [error]);

  if (props.kind === "pending") {
    const resend = async () => {
      setBusy(true);
      setError(null);
      try {
        const result = await props.onResend(props.email);
        props.onMessage(result.message);
        headingRef.current?.focus();
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

    return (
      <div className="auth-result">
        <div className="auth-card__intro">
          <p className="section-eyebrow">Sécurité du compte</p>
          <h1 id="auth-heading" ref={headingRef} tabIndex={-1}>
            Vérifie ta boîte email
          </h1>
          <p>Un lien de vérification a été envoyé à {props.email}.</p>
        </div>
        <p className="auth-success" aria-live="polite">
          {props.message}
        </p>
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
        <div className="auth-result__actions">
          <button
            className="button button--primary"
            type="button"
            onClick={resend}
            disabled={busy}
          >
            {busy ? "Veuillez patienter…" : "Renvoyer l’email"}
          </button>
          <button
            className="button button--text"
            type="button"
            onClick={props.onBackToLogin}
            disabled={busy}
          >
            Retour à la connexion
          </button>
        </div>
      </div>
    );
  }

  if (props.status === "busy") {
    return (
      <div className="auth-card__intro auth-result">
        <p className="section-eyebrow">Sécurité du compte</p>
        <h1 id="auth-heading">Vérification en cours…</h1>
        <p>Nous validons votre adresse email.</p>
      </div>
    );
  }

  const succeeded = props.status === "success";

  return (
    <div className="auth-result">
      <div className="auth-card__intro">
        <p className="section-eyebrow">Sécurité du compte</p>
        <h1 id="auth-heading" ref={headingRef} tabIndex={-1}>
          {succeeded ? "Adresse vérifiée" : "Lien de vérification invalide"}
        </h1>
        {succeeded ? (
          <p className="auth-success" aria-live="polite">
            Votre adresse est confirmée. Vous pouvez maintenant vous connecter.
          </p>
        ) : (
          <p className="auth-error" role="alert">
            Ce lien est invalide ou a expiré. Demandez-en un nouveau depuis la
            connexion.
          </p>
        )}
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

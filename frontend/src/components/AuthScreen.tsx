import { useState } from "react";

import type {
  AuthCredentials,
  AuthMessage,
} from "../api/client";
import type { AuthLink } from "../auth/link";
import { AuthCredentialsForm } from "./auth/AuthCredentialsForm";
import { PasswordResetFlow } from "./auth/PasswordResetFlow";
import { VerificationFlow } from "./auth/VerificationFlow";

type AuthView =
  | { kind: "credentials"; mode: "login" | "register" }
  | { kind: "verification-pending"; email: string; message: string }
  | { kind: "verification-result"; status: "busy" | "success" | "error" }
  | { kind: "reset-request"; message: string | null }
  | { kind: "reset-confirm"; token: string; status: "form" | "success" };

export interface AuthScreenProps {
  authLink: AuthLink | null;
  notice?: string | null;
  onLogin(credentials: AuthCredentials): Promise<void>;
  onRegister(credentials: AuthCredentials): Promise<AuthMessage>;
  onVerifyEmail(token: string): Promise<void>;
  onResendVerification(email: string): Promise<AuthMessage>;
  onRequestPasswordReset(email: string): Promise<AuthMessage>;
  onConfirmPasswordReset(token: string, password: string): Promise<void>;
}

function initialAuthView(authLink: AuthLink | null): AuthView {
  if (authLink?.kind === "verify") {
    return { kind: "verification-result", status: "busy" };
  }
  if (authLink?.kind === "reset") {
    return {
      kind: "reset-confirm",
      token: authLink.token,
      status: "form",
    };
  }
  return { kind: "credentials", mode: "login" };
}

export function AuthScreen({
  authLink,
  notice = null,
  onLogin,
  onRegister,
  onVerifyEmail,
  onResendVerification,
  onRequestPasswordReset,
  onConfirmPasswordReset,
}: AuthScreenProps) {
  const [view, setView] = useState<AuthView>(() => initialAuthView(authLink));

  const showLogin = () => {
    setView({ kind: "credentials", mode: "login" });
  };

  const showVerificationPending = (email: string, message: string) => {
    setView({ kind: "verification-pending", email, message });
  };

  let content;

  if (view.kind === "credentials") {
    content = (
      <AuthCredentialsForm
        key={view.mode}
        mode={view.mode}
        notice={notice}
        onLogin={onLogin}
        onRegister={onRegister}
        onVerificationPending={showVerificationPending}
        onSelectMode={(mode) => setView({ kind: "credentials", mode })}
        onForgotPassword={() =>
          setView({ kind: "reset-request", message: null })
        }
        onResendVerification={onResendVerification}
      />
    );
  } else if (view.kind === "verification-pending") {
    content = (
      <VerificationFlow
        kind="pending"
        email={view.email}
        message={view.message}
        onResend={onResendVerification}
        onMessage={(message) =>
          setView((current) =>
            current.kind === "verification-pending"
              ? { ...current, message }
              : current,
          )
        }
        onBackToLogin={showLogin}
      />
    );
  } else if (view.kind === "verification-result") {
    content =
      authLink?.kind === "verify" ? (
        <VerificationFlow
          kind="result"
          token={authLink.token}
          status={view.status}
          onVerify={onVerifyEmail}
          onStatus={(status) =>
            setView((current) =>
              current.kind === "verification-result"
                ? { ...current, status }
                : current,
            )
          }
          onBackToLogin={showLogin}
        />
      ) : null;
  } else if (view.kind === "reset-request") {
    content = (
      <PasswordResetFlow
        kind="request"
        message={view.message}
        onRequest={onRequestPasswordReset}
        onMessage={(message) =>
          setView((current) =>
            current.kind === "reset-request"
              ? { ...current, message }
              : current,
          )
        }
        onBackToLogin={showLogin}
      />
    );
  } else {
    content = (
      <PasswordResetFlow
        kind="confirm"
        token={view.token}
        status={view.status}
        onConfirm={onConfirmPasswordReset}
        onSuccess={() =>
          setView((current) =>
            current.kind === "reset-confirm"
              ? { ...current, status: "success" }
              : current,
          )
        }
        onBackToLogin={showLogin}
      />
    );
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="auth-heading">
        <div className="auth-brand">
          <span className="brand__name">MK-VIP</span>
          <span className="brand__description">
            MK Value Investing Platform
          </span>
        </div>
        {content}
      </section>
    </main>
  );
}

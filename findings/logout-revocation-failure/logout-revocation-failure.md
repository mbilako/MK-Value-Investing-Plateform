# Logout Failure Is Presented as Successful While the Server Session Remains Valid

## Resolution status (2026-08-14)

Remediated for v0.12.0 and tracked in GitHub issue #7. The frontend now keeps
the authenticated workspace visible when server-side logout fails, presents a
persistent accessible warning, prevents concurrent logout requests, and allows
the user to retry. Regression coverage verifies both the fail-closed path and
the successful transition to the login screen. The remainder of this report is
retained as the historical analysis of the affected revision.

## Executive Summary

The logout workflow in MK Value Investing Platform fails open in the user
interface. When `POST /auth/logout` fails, the React application catches the
error, discards it, clears only its in-memory user state, and renders the login
screen. The browser's `HttpOnly` session cookie and the corresponding
server-side session can remain valid.

On a shared browser profile, the next person can reload the application before
the session expires. The startup request to `/auth/me` then sends the retained
cookie and restores the previous user's authenticated workspace without asking
for credentials. The issue is an insufficient session expiration weakness
(CWE-613).

Revision `f04addb86654c1f93758f936132cae0fe08c17f1` is affected. No fixed
revision was available for comparison. I reviewed that revision directly and
executed the enclosed in-process proof of concept; I did not send requests to
a deployed or external instance.

The confidentiality impact is **medium** because the retained session can
expose one user's private account data. Likelihood is **low** because
exploitation requires a logout failure, later access to the same browser
profile, and reuse before normal session expiry. The resulting severity is
**low**, with remediation priority **P3**.

## Background

The application uses a React frontend and a FastAPI backend. Authentication is
represented in two places:

1. React keeps a `User` object and an `authenticated` status in memory.
2. The browser holds an `HttpOnly` cookie whose token identifies a persisted
   server-side session.

The second state is authoritative. Clearing React state hides protected
components, but it neither deletes an `HttpOnly` cookie nor revokes the
persisted session. JavaScript cannot directly remove this cookie, so the
frontend must receive a successful server logout response before it can safely
claim that logout completed.

The API client reinforces this split. All requests include browser
credentials, and `/auth/me` is the application startup check:

```typescript
// frontend/src/api/client.ts:332-359, createApiClient()
async function request<T>(
  path: string,
  options?: RequestInit,
  notifyUnauthorized = true,
): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    // ...
    throw new ApiError(
      response.status,
      getErrorMessage(errorBody, response.status),
    );
  }
  // ...
}
```

If we reload with a valid cookie, `App` calls `getCurrentUser()`. A successful
response carries the user back into the authenticated state:

```typescript
// frontend/src/App.tsx:37-51, App()
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
    // ...
    setStatus("unauthenticated");
  });
```

The security invariant is therefore simple: the UI may present logout as
complete only after the server has revoked the session and instructed the
browser to delete the cookie.

## Vulnerability Details

An authenticated user reaches the vulnerable path by selecting logout in the
workspace. The client sends a credentialed request, and explicitly disables
the global unauthorized notification for this operation:

```typescript
// frontend/src/api/client.ts:361-375, createApiClient()
return {
  getCurrentUser: () => request<User>("/auth/me", undefined, false),
  // ...
  logout: () => request<void>("/auth/logout", { method: "POST" }, false),
  // ...
};
```

Because `request()` throws for any non-success response, a network rejection,
timeout, or HTTP error such as `503 Service Unavailable` transfers control to
the `catch` in `App.logout()`. This is the root control failure:

```typescript
// frontend/src/App.tsx:72-82, App.logout()
const logout = async () => {
  try {
    await client.logout();
  } catch {
    // Local logout still succeeds when the remote session is unavailable.
  } finally {
    setUser(null);
    setNotice(null);
    setStatus("unauthenticated");
  }
};
```

The comment calls this a successful “local logout,” but the `finally` block is
only a visual state transition. It runs after both success and failure, clears
any warning, and renders the login screen. We therefore lose the only signal
that distinguishes confirmed revocation from an uncompleted request.

The backend makes the consequence precise. It first asks the authentication
service to delete and commit the session, and only then adds the cookie
deletion header:

```python
# backend/src/mkvip/api/routes/auth.py:83-98, logout()
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await service.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/api",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
```

```python
# backend/src/mkvip/auth/service.py:215-223, AuthService.logout()
async def logout(self, raw_token: str | None) -> None:
    if raw_token is None:
        return
    await self._session.execute(
        delete(SessionOrm).where(
            SessionOrm.token_hash == digest_session_token(raw_token)
        )
    )
    await self._session.commit()
```

If the request never reaches the backend, or the backend fails before the
delete commits, neither authoritative state changes: the session row remains
and the browser receives no `Set-Cookie` deletion. Nevertheless, the frontend
executes its `finally` block and shows the login screen.

We can carry that bad state into a reload:

| State | After failed request | After frontend `finally` | After reload |
| --- | --- | --- | --- |
| Server session | Valid | Valid | Valid |
| Browser cookie | Present | Present | Sent to `/auth/me` |
| React user | Present | Cleared | Restored |
| Visible screen | Workspace | Login | Workspace |

The root control failure is the blanket `catch` at `App.tsx:75`. The sink
begins with the unconditional `finally` at `App.tsx:77` and culminates in
`setStatus("unauthenticated")`. It causes the user to make a security
decision—leaving a shared browser—based on a revocation result the application
never received.

## Exploitability Analysis

The strongest practical route is a shared workstation or another situation in
which two people successively use the same browser profile. We first need the
victim to be authenticated. A transient outage then causes their logout
request to fail. Because the application shows the normal login screen with no
warning, the victim reasonably believes the session ended and leaves. The next
person restores connectivity, reloads the page, and lets the normal
`/auth/me` startup path recover the victim's identity from the retained cookie.

The next user does not need to read the token. `HttpOnly` protects it from
JavaScript disclosure, but the browser still attaches it to credentialed API
requests. This is why the existing cookie hardening does not prevent the
account restoration primitive.

Several constraints keep exploitation at low likelihood:

- The attacker cannot derive a remote, standalone exploit from this bug.
  They need access to the same browser profile.
- The logout request must fail before server-side revocation commits. A lost
  response after a successful commit may leave a stale cookie, but `/auth/me`
  will reject it, so that ordering does not produce account restoration.
- The retained session must still be within its configured lifetime.
- Merely pressing the browser's Back button is not the reliable primitive.
  React has already cleared the user object; a reload or browser restart is
  what re-runs `/auth/me` and restores authoritative state.

A person controlling the network could make the timing more reliable by
blocking the logout request, but such network control is not necessary: an
ordinary server `503`, timeout, or connectivity loss produces the same
frontend branch. Conversely, clearing cached page content is not a sufficient
defense because the credential lives in the cookie store and the session
record remains server-side.

The impact is confined to the previous user's account and the lifetime of that
specific retained session. There is no evidence here of cross-account
enumeration, token disclosure, or a way to scale the issue across unrelated
browsers. Those limits support the low overall severity while preserving the
medium confidentiality impact for the affected account.

## Proof of Concept

The enclosed PoC is a deterministic, in-process state simulator. It gives a
simulated browser a valid session cookie, makes the logout operation fail with
status `503` before revocation, applies the frontend's vulnerable
`catch`/`finally` behavior, and then simulates a reload through `/auth/me`. It
opens no listener and sends no network traffic. No real credential,
application database, or deployed environment is used.

From this report directory, run:

```sh
cd poc
powershell -NoProfile -ExecutionPolicy Bypass -File .\poc.ps1
```

Windows PowerShell 5.1 or later is required. A vulnerable run produces:

```text
[+] initial state: authenticated as victim@example.test
[+] POST /auth/logout returned 503
[+] vulnerable UI state after failure: unauthenticated
[+] browser cookie retained: mkvip_session=demo-session
[+] reload /auth/me returned 200
[+] restored state: authenticated as victim@example.test
[+] demonstration complete: fail-open logout confirmed
```

The PoC changes only in-memory variables, so no cleanup is required. It exits
nonzero if the cookie is lost, `/auth/me` rejects the session, or the account
is not restored.

On a fixed frontend, the failed logout would leave the UI authenticated (or in
an explicit `logout_failed` state), display an unambiguous warning, and invite
the user to retry. In that case, the PoC's simulated transition to the login
screen would no longer match application behavior.

## Remediation

The frontend must restore this invariant: **only a confirmed successful logout
response may transition the UI to the ordinary unauthenticated screen**. A
failure must remain visibly distinct and must tell the user that the server
session may still be active.

A minimal fail-closed change is:

```typescript
// frontend/src/App.tsx
const logout = async () => {
  try {
    await client.logout();
  } catch {
    window.alert(
      "La déconnexion a échoué. Votre session est encore active. " +
        "Réessayez avant de quitter cet appareil.",
    );
    return;
  }

  setUser(null);
  setNotice(null);
  setStatus("unauthenticated");
};
```

This narrow patch keeps the authenticated workspace state when revocation
fails and makes the failure visible. A production-quality implementation
should replace the blocking alert with a persistent, accessible error banner
and an explicit retry action. It may also introduce a `logging_out` state to
prevent duplicate requests without conflating an in-progress operation with
successful logout.

Additional hardening should include:

- Make logout idempotent so the frontend can retry safely after ambiguous
  network failures.
- Where a response can still be generated, expire the browser cookie even
  when server-side cleanup encounters an error, while continuing to report
  that authoritative revocation was not confirmed.
- Keep server sessions reasonably short and revoke them on other security
  events. This limits the window but does not replace correct logout feedback.
- Log logout failures without logging raw tokens, so operators can measure and
  investigate failed revocations.

Regression coverage should exercise the real state transition:

1. Reject `client.logout()` with a network error and assert that the workspace
   remains visible, the login screen does not appear, and a persistent warning
   is shown.
2. Return HTTP 503 and assert the same fail-closed behavior.
3. Resolve logout successfully and assert that the workspace is cleared and
   the login screen appears.
4. In an integration test, create a session, fail logout before the server
   commit, retain the cookie, and verify that `/auth/me` remains authenticated
   while the frontend reports logout failure.
5. Retry logout successfully, then verify that the cookie is expired and
   `/auth/me` returns `401 Unauthorized`.

## Summary

The application currently treats removal of React state as equivalent to
session revocation. When `POST /auth/logout` fails, that equivalence breaks:
the UI reports success while both the cookie and server session may remain
valid. We traced the transition from the credentialed client request through
the swallowed exception to the unconditional unauthenticated state, then
demonstrated locally that a reload restores the previous account.

The realistic exploitation path requires an outage and later access to the
same browser profile, which makes likelihood low. For the affected user,
however, the result can be unauthorized access to private account data.
Future variant analysis should review every UI action that changes
authentication state—session expiry, password changes, account deactivation,
and global logout—to ensure that local presentation never outruns
authoritative server state.

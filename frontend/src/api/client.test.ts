import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client authentication", () => {
  it("sends credentials and exposes the authenticated user", async () => {
    const expectedUser = {
      id: "user-1",
      email: "alice@example.com",
      created_at: "2026-07-26T10:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify(expectedUser),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient();

    await expect(client.getCurrentUser()).resolves.toEqual(expectedUser);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/me",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("registers without treating the account as authenticated", async () => {
    const credentials = { email: "alice@example.com", password: "new-password" };
    const expectedMessage = {
      message:
        "Si cette adresse peut être inscrite, un email de vérification a été envoyé.",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expectedMessage), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createApiClient().register(credentials)).resolves.toEqual(
      expectedMessage,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(credentials),
        credentials: "include",
      }),
    );
  });

  it("submits verification and reset tokens only in JSON bodies", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient();

    await expect(client.verifyEmail("verification-token-value")).resolves.toBeUndefined();
    await expect(
      client.confirmPasswordReset(
        "reset-token-value",
        "new correct horse battery",
      ),
    ).resolves.toBeUndefined();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/verify-email");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/auth/password-reset/confirm",
    );
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ token: "verification-token-value" }),
    );
    expect(fetchMock.mock.calls[1][1]?.body).toBe(
      JSON.stringify({
        token: "reset-token-value",
        password: "new correct horse battery",
      }),
    );
  });

  it("resends a verification email and returns the generic accepted message", async () => {
    const expectedMessage = {
      message:
        "Si un compte non vérifié utilise cette adresse, un email de vérification a été envoyé.",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expectedMessage), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createApiClient().resendVerification("investor@example.com"),
    ).resolves.toEqual(expectedMessage);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/resend-verification",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "investor@example.com" }),
        credentials: "include",
      }),
    );
  });

  it("requests a password reset and returns the generic accepted message", async () => {
    const expectedMessage = {
      message:
        "Si un compte utilise cette adresse, un email de réinitialisation a été envoyé.",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expectedMessage), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createApiClient().requestPasswordReset("investor@example.com"),
    ).resolves.toEqual(expectedMessage);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/password-reset/request",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "investor@example.com" }),
        credentials: "include",
      }),
    );
  });

  it("logs in with the submitted credentials and returns the authenticated user", async () => {
    const credentials = { email: "alice@example.com", password: "correct-password" };
    const expectedUser = {
      id: "user-1",
      email: "alice@example.com",
      created_at: "2026-07-26T10:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expectedUser), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createApiClient().login(credentials)).resolves.toEqual(
      expectedUser,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(credentials),
        credentials: "include",
      }),
    );
  });

  it("notifies subscribers once when any request returns 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
    );
    const client = createApiClient();
    const handler = vi.fn();
    client.onUnauthorized(handler);

    await expect(client.listCompanies()).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("keeps an invalid login inside the authentication form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
    );
    const client = createApiClient();
    const handler = vi.fn();
    client.onUnauthorized(handler);

    await expect(
      client.login({ email: "alice@example.com", password: "wrong-password" }),
    ).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
  });

  it("accepts the empty 204 logout response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createApiClient().logout()).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("preserves a non-401 API error without notifying subscribers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Email already registered" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const client = createApiClient();
    const handler = vi.fn();
    client.onUnauthorized(handler);

    const request = client.listCompanies();

    await expect(request).rejects.toMatchObject({
      status: 409,
      message: "Email already registered",
    });
    await expect(request).rejects.toBeInstanceOf(ApiError);
    expect(handler).not.toHaveBeenCalled();
  });

  it("formats structured FastAPI validation details as a safe message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              {
                type: "value_error",
                loc: ["body", "email"],
                msg: "value is not a valid email address: An email address must have an @-sign.",
                input: "not-an-email",
                ctx: {
                  reason: "An email address must have an @-sign.",
                },
              },
            ],
          }),
          {
            status: 422,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    const request = createApiClient().register({
      email: "not-an-email",
      password: "valid-password",
    });

    await expect(request).rejects.toMatchObject({
      status: 422,
      message:
        "value is not a valid email address: An email address must have an @-sign.",
    });
  });
});

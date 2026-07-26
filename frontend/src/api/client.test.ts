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

  it("registers with the submitted credentials and returns the created user", async () => {
    const credentials = { email: "alice@example.com", password: "new-password" };
    const expectedUser = {
      id: "user-1",
      email: "alice@example.com",
      created_at: "2026-07-26T10:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expectedUser), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createApiClient().register(credentials)).resolves.toEqual(
      expectedUser,
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

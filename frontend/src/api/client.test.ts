import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client authentication", () => {
  it("sends credentials and exposes the authenticated user", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "user-1",
          email: "alice@example.com",
          created_at: "2026-07-26T10:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient();

    await client.getCurrentUser();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/me",
      expect.objectContaining({ credentials: "include" }),
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
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    await expect(createApiClient().logout()).resolves.toBeUndefined();
  });
});

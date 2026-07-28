import { describe, expect, it, vi } from "vitest";

import { readAndClearAuthLink } from "./link";

describe("authentication links", () => {
  it("reads a verification token and clears it from browser history", () => {
    const replaceState = vi.fn();
    const result = readAndClearAuthLink(
      {
        hash: "#verify-email=verification-token",
        pathname: "/",
        search: "?source=mail",
      },
      { replaceState },
    );

    expect(result).toEqual({
      kind: "verify",
      token: "verification-token",
    });
    expect(replaceState).toHaveBeenCalledWith(null, "", "/?source=mail");
  });

  it("ignores unknown or empty fragments without changing history", () => {
    const replaceState = vi.fn();
    expect(
      readAndClearAuthLink(
        { hash: "#unknown=value", pathname: "/", search: "" },
        { replaceState },
      ),
    ).toBeNull();
    expect(replaceState).not.toHaveBeenCalled();
  });

  it("clears a recognized malformed fragment without throwing", () => {
    const replaceState = vi.fn();
    expect(
      readAndClearAuthLink(
        { hash: "#verify-email=%ZZ", pathname: "/", search: "" },
        { replaceState },
      ),
    ).toBeNull();
    expect(replaceState).toHaveBeenCalledWith(null, "", "/");
  });

  it("copies a live location token before clearing browser history", () => {
    let hash = "#reset-password=reset-token";
    const replaceState = vi.fn(() => {
      hash = "";
    });

    expect(
      readAndClearAuthLink(
        {
          get hash() {
            return hash;
          },
          pathname: "/",
          search: "",
        },
        { replaceState },
      ),
    ).toEqual({ kind: "reset", token: "reset-token" });
    expect(hash).toBe("");
  });
});

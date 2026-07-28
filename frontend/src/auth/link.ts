export type AuthLink =
  | { kind: "verify"; token: string }
  | { kind: "reset"; token: string };

interface AuthLinkLocation {
  hash: string;
  pathname: string;
  search: string;
}

interface AuthLinkHistory {
  replaceState(data: unknown, unused: string, url?: string | URL | null): void;
}

const prefixes = [
  { value: "#verify-email=", kind: "verify" },
  { value: "#reset-password=", kind: "reset" },
] as const;

export function readAndClearAuthLink(
  location: AuthLinkLocation,
  history: AuthLinkHistory,
): AuthLink | null {
  const prefix = prefixes.find(({ value }) => location.hash.startsWith(value));
  if (!prefix) {
    return null;
  }

  const encodedToken = location.hash.slice(prefix.value.length);
  history.replaceState(
    null,
    "",
    `${location.pathname}${location.search}`,
  );

  try {
    const token = decodeURIComponent(encodedToken);
    return token ? { kind: prefix.kind, token } : null;
  } catch {
    return null;
  }
}

/**
 * Local Keycloak-backed auth for self-hosted agent-canvas.
 * Enabled when VITE_LOCAL_AUTH_ENABLED is "true" or "1".
 */

export type LocalAuthUser = {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  credit_balance: number;
};

export function isLocalAuthEnabled(): boolean {
  const raw = (
    import.meta.env.VITE_LOCAL_AUTH_ENABLED ??
    (typeof window !== "undefined"
      ? (window as { __VITE_LOCAL_AUTH_ENABLED__?: string })
          .__VITE_LOCAL_AUTH_ENABLED__
      : undefined) ??
    ""
  )
    .toString()
    .toLowerCase();
  return raw === "true" || raw === "1";
}

function authBase(): string {
  // Same-origin via ingress; optional override for split-host setups.
  const base =
    import.meta.env.VITE_LOCAL_AUTH_BASE_URL ||
    import.meta.env.VITE_BACKEND_BASE_URL ||
    "";
  return base.replace(/\/+$/, "");
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail && typeof body.detail === "object") {
      if (typeof body.detail.message === "string") return body.detail.message;
      return JSON.stringify(body.detail);
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

export async function fetchLocalMe(): Promise<LocalAuthUser | null> {
  const res = await fetch(`${authBase()}/api/auth/me`, {
    credentials: "include",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as LocalAuthUser;
}

export async function localLogin(
  username: string,
  password: string,
): Promise<LocalAuthUser> {
  const res = await fetch(`${authBase()}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as LocalAuthUser;
}

export async function localLogout(): Promise<void> {
  await fetch(`${authBase()}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export type AdminUserSummary = {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  is_active: boolean;
  credit_balance: number;
  credit_limit: number;
};

export async function fetchAdminUsers(): Promise<AdminUserSummary[]> {
  const res = await fetch(`${authBase()}/api/admin/users`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AdminUserSummary[];
}

export async function setAdminUserCredits(
  userId: string,
  body: { balance?: number; delta?: number; credit_limit?: number },
): Promise<{ balance: number; credit_limit: number }> {
  const res = await fetch(`${authBase()}/api/admin/users/${userId}/credits`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { balance: number; credit_limit: number };
}

export async function setAdminUserActive(
  userId: string,
  active: boolean,
): Promise<void> {
  const path = active ? "enable" : "disable";
  const res = await fetch(`${authBase()}/api/admin/users/${userId}/${path}`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function createAdminUser(body: {
  username: string;
  password: string;
  email?: string;
  is_admin?: boolean;
  initial_credits?: number;
}): Promise<AdminUserSummary> {
  const res = await fetch(`${authBase()}/api/admin/users`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AdminUserSummary;
}

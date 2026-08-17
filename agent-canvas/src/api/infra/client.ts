/**
 * Infra servers API (local gateway).
 */

function infraBase(): string {
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
    return JSON.stringify(body?.detail ?? body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

export type InfraServer = {
  id: string;
  name: string;
  hostname: string;
  port: number;
  username: string;
  auth_type: string;
  description: string | null;
  tags: string[];
  is_active: boolean;
  last_seen_at: string | null;
  last_error: string | null;
};

export async function fetchInfraServers(): Promise<InfraServer[]> {
  const res = await fetch(`${infraBase()}/api/infra/servers`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createInfraServer(body: {
  name: string;
  hostname: string;
  port?: number;
  username: string;
  auth_type?: string;
  description?: string;
  tags?: string[];
  credential?: string;
}): Promise<InfraServer> {
  const res = await fetch(`${infraBase()}/api/infra/servers`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateInfraServer(
  serverId: string,
  body: {
    name?: string;
    hostname?: string;
    port?: number;
    username?: string;
    auth_type?: string;
    description?: string;
    tags?: string[];
    is_active?: boolean;
  },
): Promise<InfraServer> {
  const res = await fetch(`${infraBase()}/api/infra/servers/${serverId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteInfraServer(serverId: string): Promise<void> {
  const res = await fetch(`${infraBase()}/api/infra/servers/${serverId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function setInfraCredentials(
  serverId: string,
  body: { credential: string; passphrase?: string; auth_type?: string },
): Promise<void> {
  const res = await fetch(
    `${infraBase()}/api/infra/servers/${serverId}/credentials`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) throw new Error(await parseError(res));
}

export async function testInfraServer(
  serverId: string,
): Promise<{ ok: boolean; duration_ms?: number; stdout?: string }> {
  const res = await fetch(`${infraBase()}/api/infra/servers/${serverId}/test`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchInfraGpu(serverId: string): Promise<{
  gpus: Array<Record<string, unknown>>;
  reason: string | null;
  cached: boolean;
}> {
  const res = await fetch(`${infraBase()}/api/infra/servers/${serverId}/gpu`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchInfraServices(serverId: string): Promise<{
  services: Array<{
    unit_name: string;
    active_state: string | null;
    sub_state: string | null;
    description: string | null;
  }>;
}> {
  const res = await fetch(
    `${infraBase()}/api/infra/servers/${serverId}/services`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function infraServiceAction(
  serverId: string,
  unit: string,
  action: "restart" | "stop",
): Promise<{ ok: boolean }> {
  const res = await fetch(
    `${infraBase()}/api/infra/servers/${serverId}/services/${encodeURIComponent(unit)}/action`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

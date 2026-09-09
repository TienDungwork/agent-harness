/**
 * Infra servers API (local gateway).
 */

import { resolveLocalGatewayBaseUrl } from "#/api/local-gateway-base-url";

function infraBase(): string {
  return resolveLocalGatewayBaseUrl();
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

// ── Monitor (Beszel proxy) ────────────────────────────────────────────────────

export type BeszelSystemInfo = {
  u: number; // uptime seconds
  cpu: number; // CPU %
  mp: number; // memory %
  dp: number; // disk %
  v: string; // agent version
  bb: number; // bandwidth bytes
  la?: [number, number, number]; // load avg 1/5/15m
  dt?: number; // dashboard temp °C
  g?: number; // GPU %
};

export type BeszelSystem = {
  id: string;
  name: string;
  host: string;
  port: string;
  status: "up" | "down" | "paused" | "pending";
  info: BeszelSystemInfo;
  created: string;
  updated: string;
};

export type BeszelStatRecord = {
  id: string;
  system: string;
  type: string;
  stats: {
    cpu: number;
    m: number; // total mem GB
    mu: number; // used mem GB
    mp: number; // mem %
    d: number; // disk total GB
    du: number; // disk used GB
    dp: number; // disk %
    ns: number; // net sent MB/s
    nr: number; // net recv MB/s
    la: [number, number, number];
    t?: Record<string, number>; // temperatures
  };
  created: string;
};

export async function fetchMonitorSystems(): Promise<{
  items: BeszelSystem[];
  totalItems: number;
}> {
  const res = await fetch(`${infraBase()}/api/monitor/systems`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchMonitorStats(
  systemId: string,
  type: "1m" | "10m" | "20m" | "120m" | "480m" = "10m",
): Promise<{ items: BeszelStatRecord[]; totalItems: number }> {
  const res = await fetch(
    `${infraBase()}/api/monitor/systems/${systemId}/stats?type=${type}`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchMonitorContainers(systemId: string): Promise<{
  items: Array<{
    id: string;
    name: string;
    status: string;
    stats: Record<string, unknown>;
  }>;
}> {
  const res = await fetch(
    `${infraBase()}/api/monitor/systems/${systemId}/containers`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deployBeszelAgent(serverId: string): Promise<{
  ok: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
}> {
  const res = await fetch(
    `${infraBase()}/api/infra/servers/${serverId}/deploy-beszel`,
    { method: "POST", credentials: "include" },
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

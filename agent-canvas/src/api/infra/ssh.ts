import { resolveLocalGatewayBaseUrl } from "#/api/local-gateway-base-url";

/**
 * Build WebSocket URL for interactive SSH to an infra server.
 */
export function infraSshWsUrl(serverId: string, cols = 120, rows = 32): string {
  const base = resolveLocalGatewayBaseUrl() || window.location.origin;
  const u = new URL(base);
  const proto = u.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${u.host}/api/infra/servers/${serverId}/ssh?cols=${cols}&rows=${rows}`;
}

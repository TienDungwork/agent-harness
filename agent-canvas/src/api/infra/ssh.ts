/**
 * Build WebSocket URL for interactive SSH to an infra server.
 */
export function infraSshWsUrl(
  serverId: string,
  cols = 120,
  rows = 32,
): string {
  const base =
    import.meta.env.VITE_LOCAL_AUTH_BASE_URL ||
    import.meta.env.VITE_BACKEND_BASE_URL ||
    (typeof window !== "undefined" ? window.location.origin : "");
  const u = new URL(base || window.location.origin);
  const proto = u.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${u.host}/api/infra/servers/${serverId}/ssh?cols=${cols}&rows=${rows}`;
}

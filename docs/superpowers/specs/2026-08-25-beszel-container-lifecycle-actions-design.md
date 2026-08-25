# Beszel container lifecycle actions (SSH via gateway) — Design

**Date:** 2026-08-25  
**Status:** Approved for implementation

## Goal

On Beszel’s Containers page, admins can right-click a container row and run **Start / Stop / Restart**. local-gateway resolves the host, SSHs in with InfraServer credentials, and runs `docker start|stop|restart`.

## Why

Beszel today is monitoring-only. Admins need lifecycle control on the same table without opening a separate SSH terminal.

## Decisions

| Topic | Choice |
|-------|--------|
| Operations | Start, Stop, Restart only |
| Trigger | Right-click anywhere on the container row (no `⋯` column) |
| Menu look | Reuse Beszel native menu styles (font, colors, spacing) |
| Confirm | Start immediate; Stop and Restart use Beszel-style confirm dialog |
| Idle enablement | Running → Start dimmed, Stop + Restart enabled; stopped → only Start enabled |
| In-flight lock | After one action is chosen, other items stay dimmed until that call finishes, then recompute from new state |
| Who may act | Gateway `require_admin` only; non-admins get no usable menu (or all items disabled) |
| Execution | Beszel UI → local-gateway → SSH → `docker start\|stop\|restart` |
| Not used | beszel-agent docker.sock write path; Creanova AI agent; logs/exec/pause |

## UX

1. Admin right-clicks a Containers table row.
2. Context menu shows exactly three items: **Start | Stop | Restart**, styled like existing Beszel menus.
3. Invalid actions for current status are visible but disabled (dimmed).
4. Choosing **Stop** or **Restart** opens a confirm dialog; **Start** runs immediately.
5. While the gateway request is in flight, other menu actions for that row stay disabled until completion.
6. Success/failure uses Beszel-native toast or equivalent feedback; table status updates via existing container polling.

## APIs (local-gateway)

Admin-only. Auth from Beszel reuses the pin bridge: PocketBase JWT → gateway user by email → `is_admin`.

Suggested shape (exact paths may match neighboring infra routes):

- `POST /api/infra/containers/start`
- `POST /api/infra/containers/stop`
- `POST /api/infra/containers/restart`

Body (minimum):

```json
{
  "host": "<InfraServer.hostname / Beszel system.host>",
  "container_name": "<name>",
  "container_id": "<optional short or full id>"
}
```

Optional: `server_id` when the UI already knows the InfraServer id.

Behavior:

1. `require_admin`.
2. Resolve `InfraServer` by `server_id` or by `hostname == host` (same match key used in beszel-bootstrap system sync).
3. Load decrypted SSH credentials; fail clearly if missing/offline.
4. SSH run: `docker start|stop|restart` preferring `container_id` when present, else `container_name` (shell-safe quoting).
5. Return stdout/stderr excerpt + exit code; non-zero → HTTP error with message for UI toast.

## Host mapping

Beszel `ContainerRecord.system` → system record → `host` field.  
That `host` must equal `InfraServer.hostname` (already how bootstrap sync matches systems). If no InfraServer row / credentials → error, do not invent SSH.

## UI touchpoints

- Primary: `services/beszel/internal/site/src/components/containers-table/` (row `onContextMenu`, menu, confirm, in-flight state).
- Auth header to gateway: same pattern as Creanova pin calls from Beszel UI (`/creanova-api` or equivalent proxy).
- Do **not** implement the menu via `beszel_branding.js` DOM injection (fragile vs virtual table).

## Affected areas

| Area | Role |
|------|------|
| Beszel Containers table (TS/React) | Context menu + confirm + call gateway |
| `services/local-gateway/routers/infra.py` | New container lifecycle endpoints |
| `services/local-gateway/infra/ssh_client.py` | Reuse existing `run_ssh` |
| Nginx / Beszel proxy | Ensure Beszel origin can reach gateway infra APIs (same as pins) |
| Deploy docs | Note admin-only SSH lifecycle; no agent socket RW change |

## Out of scope (MVP)

- Pause / unpause
- Logs, exec, attach, remove, recreate
- Non-admin operators
- Writing through beszel-agent Docker API / RW docker.sock
- Bulk actions on multiple rows
- Vector / agent handoff from this menu

## Implementation notes (resolve during build)

- Prefer Docker container id over name when both are available.
- SSH timeout and error copy for host unreachable / auth failure / docker missing.
- Confirm dialog copy should include container name (and host if multi-system table).
- After success, rely on existing container list refresh; no need to invent a second status channel.

## Success criteria

- Admin right-click Start/Stop/Restart works end-to-end on a host with InfraServer credentials.
- Non-admin cannot invoke the API (403) and has no usable menu.
- Stop/Restart always confirm; Start does not.
- Concurrent second action on the same row is blocked until the first completes.
- Menu visually matches existing Beszel controls.

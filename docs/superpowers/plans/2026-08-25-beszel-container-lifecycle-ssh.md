# Beszel container lifecycle (SSH) — Implementation Plan

> **For agentic workers:** Inline execution in this session (user asked triển khai).

**Goal:** Admin right-click Start/Stop/Restart on Beszel Containers; local-gateway SSHs and runs docker.

**Architecture:** Beszel UI → `/creanova-api` → local-gateway (`require_admin` via `get_auth_user` + `is_admin`) → InfraServer SSH → `docker start|stop|restart`.

**Tech Stack:** FastAPI, asyncssh, React/Lingui Beszel site, existing pin auth (`X-Beszel-Token`).

## Global Constraints

- Start/Stop/Restart only; admin only; Start no confirm; Stop/Restart confirm
- Prefer `container_id` over name; `shlex.quote`
- Do not use beszel-agent docker.sock write path
- Menu: native Beszel DropdownMenu styles at cursor (no new ContextMenu dependency)
- Commit format: `beta vX.Y.Z: …` in OpenHands repo; conventional ok in nested `services/beszel` fork

---

### Task 1: Gateway lifecycle helpers + API

**Files:**
- Create: `services/local-gateway/infra/container_lifecycle.py`
- Modify: `services/local-gateway/routers/infra.py`
- Test: `services/local-gateway/tests/test_container_lifecycle.py`
- Modify: `agent-canvas/docker/beszel-ui-nginx.conf` (proxy_read_timeout ≥ 90s)

**Produces:**
- `build_docker_lifecycle_command(action, container_id, container_name) -> str`
- `POST /api/infra/containers/{start|stop|restart}`

- [ ] Helper + unit tests for command build / id preference / invalid action
- [ ] Endpoints: auth via `get_auth_user`, reject non-admin 403, resolve host → InfraServer, SSH, audit
- [ ] Commit OpenHands side

### Task 2: Beszel UI context menu

**Files:**
- Create: `services/beszel/internal/site/src/lib/creanova-container-actions.ts`
- Modify: `services/beszel/internal/site/src/components/containers-table/containers-table.tsx`
- Nested commit in `services/beszel`

**Produces:**
- `runContainerAction(action, {host, container_name, container_id})`
- Row `onContextMenu` + DropdownMenu + AlertDialog for Stop/Restart

- [ ] Client module (same gatewayFetch pattern as pins)
- [ ] Wire menu + enablement + in-flight lock + toasts
- [ ] Commit nested beszel + OpenHands CHANGELOG bump

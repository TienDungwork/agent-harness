# Beszel Keycloak + per-user pinned containers — Design

**Date:** 2026-08-21  
**Status:** Approved for implementation

## Goal

Share Keycloak identity with Beszel monitor UI (`:18090`). Users pin containers on Beszel; pins store in local-gateway DB scoped by Creanova user (email match). Agents search pins via gateway.

## Decisions

| Topic | Choice |
|-------|--------|
| Pin UX | Beszel UI (inject JS), not Canvas settings |
| Pin scope | Per user (Keycloak / gateway user by email) |
| Store | `infra_pinned_containers` on local-gateway |
| Search | SQL ILIKE on name/host/image/tags/note (no vector) |
| Beszel login | Keycloak OIDC client `beszel` + PocketBase OAuth2 on `users` (configured via `_superusers` like SMTP) |
| Service account | Keep `admin@creanova.local` password user for bootstrap sync; do **not** set `DISABLE_PASSWORD_AUTH` |
| OIDC users | `USER_CREATION=true` so Keycloak users auto-create on first Beszel login |
| Pin auth from Beszel | PocketBase JWT → gateway resolves email via Beszel auth-refresh → map to gateway `User.email` |
| Agent auth | `X-Creanova-Infra-Token` (+ optional `user_email` / `user_id`); session cookie also works |
| Superuser | Existing `_superusers` account (same email/password as hub user) configures OIDC/SMTP only |

## APIs

- `GET /api/infra/pinned-containers` — list current user's pins
- `GET /api/infra/pinned-containers/search?q=` — ranked search (exact/prefix/substring)
- `POST /api/infra/pinned-containers` — upsert pin `{host, container_name, container_id?, image?, tags?, note?, server_id?}`
- `DELETE /api/infra/pinned-containers/{id}`

## Agent

- MCP tool `infra_search_pinned_containers`
- LOCAL_HARNESS: search pins before focusing container work

## Out of scope (MVP)

- Vector search
- Disable password auth on Beszel
- Pin sync into PocketBase collections
- Auto-pin from GPU metrics

# Remote SSH harness (InfraServer) — Design

**Date:** 2026-08-21  
**Status:** Approved for implementation

## Goal

Chat prompts like `ssh vào 192.168.1.250` resolve a host from Settings → Host (`InfraServer`) and let the agent run follow-up shell commands on that machine via local-gateway (credentials never leave the gateway).

## Decisions

| Topic | Choice |
|-------|--------|
| Transport | Gateway SSH exec (`run_ssh`), not interactive PTY |
| Lookup | Indexed exact/prefix SQL on `hostname`/`name`/`tags` (no vector) |
| Sticky target | Agent remembers `server_id` in-conversation after resolve |
| Shell | Full remote shell (MVP) |
| Deletes | Always ask user; API returns `needs_confirmation` unless `confirm_destructive=true` |
| Agent auth | `X-Creanova-Infra-Token` (= `INFRA_AGENT_TOKEN`) acts as admin operate |

## APIs

- `GET /api/infra/servers/resolve?q=` → ranked matches `{items:[{id,name,hostname,port,username,...}], query}`
- `POST /api/infra/servers/{id}/run` body `{command, confirm_destructive?, timeout_sec?}` → stdout/stderr/exit_code or 409 needs_confirmation

## Prompt

Extend `<LOCAL_HARNESS>` with resolve → set target → run rules and destructive confirm rule.

## Out of scope (MVP)

- Vector / embedding search
- Persistent PTY session
- Injecting private keys into the agent sandbox

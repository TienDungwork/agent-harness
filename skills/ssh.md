---
name: SSH Microagent
type: knowledge
version: 1.1.0
agent: CodeActAgent
triggers:
  - ssh
  - remote server
  - remote machine
  - remote host
  - remote connection
  - secure shell
  - ssh keys
---

# SSH Microagent (Creanova harness)

On this self-hosted Canvas, do **not** ask for IP/username/private key and do
**not** invent TEST-NET addresses. Inventory is Settings → Host.

1. `GET /api/infra/servers/resolve?q=<token>` — token may be a last octet (`250`).
   Header: `X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN`.
2. Sticky `server_id` from the top match. Confirm name/IP/user in one line.
3. `POST /api/infra/servers/{id}/run` with the command. Destructive ops need
   an explicit yes, then `confirm_destructive: true`.

---
name: ssh
description: Resolve hosts from Settings → Host and run remote commands via the Creanova SSH harness (gateway APIs). Use when the user says ssh, remote host, or a last IP octet like 250.
triggers:
- ssh
- remote server
- remote machine
- remote host
- remote connection
- secure shell
- ssh keys
---

# SSH Skill (Creanova harness)

On this self-hosted Agent Canvas, SSH inventory lives in **Settings → Host**. Credentials stay on local-gateway. Do **not** run interactive `ssh user@host`, do **not** ask for a password or private key, and do **not** invent IPs (no TEST-NET / 191.0.2.1).

## First action (always)

When the user says "ssh vào 250", "ssh 191", "ssh to gpu-box", or similar:

1. Take their token as `q` even if it is only a last IPv4 octet (`250`, `191`).
2. Call resolve immediately (do not ask for a fuller IP first):

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/servers/resolve?q=TOKEN"
```

3. Pick `items[0]`. Remember `id` as the sticky `server_id` for this chat.
4. Reply with one line: name, hostname, username. If they already asked for a command, run it. Otherwise wait.
5. If `count=0`, `GET /api/infra/servers` and tell them the host is missing from Settings → Host.

## Run commands

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command":"uname -a","confirm_destructive":false,"timeout_sec":120}' \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/servers/SERVER_ID/run"
```

Destructive commands (`rm`, `dd`, `mkfs`, …) need an explicit yes in chat, then `confirm_destructive: true`.

## Fallback only

Use local `ssh` / `scp` / `~/.ssh/config` only when the user explicitly wants a key on this machine and the host is **not** in Settings → Host. Windows notes: `references/windows.md`.

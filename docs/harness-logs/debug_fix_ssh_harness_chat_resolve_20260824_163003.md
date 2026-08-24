# Execution log: SSH chat does not resolve hosts

- **Category**: debug_fix
- **Task**: Agent chat "ssh vào 250/191" asks for IP instead of resolving Settings → Host
- **Started**: 2026-08-24 16:30:03
- **Pipeline**: 4a — `04-bugfinder` → `05-fix` → `06-test`

## 04-bugfinder

- **Status**: complete
- **Goal**: Explain why Canvas chat never SSHs after "ssh vào 250" / "ssh vào 191"
- **Scope**: Skill `ssh` trigger, LOCAL_HARNESS, GET /api/infra/servers/resolve ranking
- **Constraints**: Read-only diagnosis
- **Files / modules**: `packages/extensions/skills/ssh/SKILL.md`, `src/config/local-agent-prompt.ts`, `services/local-gateway/infra/resolve.py`
- **Decisions**: Primary cause = keyword-triggered generic SSH skill (Skill Ready) instructs ask-for-IP/key; LOCAL_HARNESS loses. Secondary = query "250" is only substring score 20 vs names containing 250. Token in sandbox is a follow-up risk, not this transcript (no tool calls).
- **Open questions**: none for this symptom
- **Verification target**: Chat "ssh vào 250" must call resolve, not invent 191.0.2.1

## 05-fix

- **Status**: complete
- **Goal**: Make "ssh vào 250" resolve inventory and stop the generic SSH Q&A
- **Scope**: ssh SKILL.md + catalog, LOCAL_HARNESS, SOUL.md, last-octet ranking
- **Constraints**: Do not commit unrelated dirty tree
- **Files / modules**: `packages/extensions/skills/ssh/SKILL.md`, `src/config/local-agent-prompt.ts`, `config/SOUL.md`, `services/local-gateway/infra/resolve.py`, `skills/ssh.md`
- **Decisions**: Rewrite ssh skill to gateway-first; last octet score 70; SOUL.md bind-mount for immediate identity
- **Open questions**: none — overlay rebuilt and agent-canvas restarted
- **Verification target**: pytest last-octet; vitest LOCAL_HARNESS contains last IPv4 octet

## 06-test

- **Status**: complete
- **Goal**: Prove last-octet ranking and harness prompt
- **Scope**: `tests/test_infra_resolve_run.py`, adapter suffix test
- **Constraints**: none
- **Files / modules**: listed above
- **Decisions**: regression test that '250' beats name substring 250-backup
- **Open questions**: none
- **Verification target**: 5 pytest passed; vitest adapter harness test passed

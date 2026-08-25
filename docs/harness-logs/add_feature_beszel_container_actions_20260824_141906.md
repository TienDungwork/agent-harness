# Execution log: Beszel container actions

- **Category**: add_feature
- **Task**: Clarify and design container operations in the Beszel Containers UI
- **Started**: 2026-08-24 14:19:06
- **Pipeline**: 2 (ambiguous implementation) — `01-brainstorm` → approval → later skills

## 01-brainstorm

- **Status**: complete (design approved)
- **Goal**: Interpret “thao tác với container” in Beszel Containers and lock scope before any implementation
- **Scope**: Lifecycle only (start / stop / restart) via right-click on Containers row; admin only; local-gateway SSH to InfraServer host
- **Constraints**: No logs/exec/pause; no beszel-agent RW docker.sock; no Creanova AI agent handoff; native Beszel menu styling
- **Files / modules**: `services/beszel/internal/site/.../containers-table/`, `services/local-gateway/routers/infra.py`, SSH client, Beszel→gateway auth bridge (pins pattern)
- **Decisions**:
  - Operations = start / stop / restart only
  - Trigger = right-click anywhere on the row
  - Menu = Beszel-native look; Start | Stop | Restart only
  - Confirm = Start immediate; Stop and Restart confirm
  - Idle enablement by container state; in-flight lock until request completes
  - Who may act = admin only (`require_admin`)
  - Execution = Beszel UI → local-gateway → SSH → docker
- **Open questions**: None for product intent (id vs name preference deferred to implement)
- **Verification target**: Design approved; spec at `docs/superpowers/specs/2026-08-25-beszel-container-lifecycle-actions-design.md`
- **Handoff**: After user reviews written spec → `02-plan` / writing-plans

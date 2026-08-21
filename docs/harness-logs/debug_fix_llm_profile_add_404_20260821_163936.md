# Execution Log: debug_fix_llm_profile_add_404

## Task
Adding a new LLM/agent profile (Qwen 3.8) shows `HTTP request failed (404 Not Found): {"detail":"Not found"}`.

## Pipeline
04-bugfinder → 05-fix → 06-test → 07-review

## Status
Complete

## 04-bugfinder

### Symptom
UI toast: `HTTP request failed (404 Not Found): {"detail":"Not found"}` after adding Qwen 3.8 profile.

### Evidence
- POST `/api/profiles/qwen-3.8-27B` → 201 (save works)
- POST `/api/agent-profiles/qwen3.8` → 201 (save works)
- Gateway access log: `POST /api/auth/workspace-session` → 404
- `proxy.py` catch-all 404s every `/api/auth/*` so agent-server `workspace-session` never forwards
- TypeScript `HttpError` formats exactly as the toast
- Qwen profile `base_url` is host root (no `/v1`); tunnel `/` returns `{"detail":"Not Found"}`, `/v1/models` exists (401)

### Root cause #1 (toast, High)
Gateway blocks forwarding of `/api/auth/workspace-session` to agent-server.

### Root cause #2 (Qwen run, High)
LLM profile `qwen-3.8-27B` `base_url` missing `/v1`; LiteLLM then hits host `/chat/completions` → 404. Logs also: `model 'qwen-3.8-27B' not found`.

## 05-fix

- `services/local-gateway/proxy.py` — stop 404ing `/api/auth/*` on the catch-all so `workspace-session` forwards
- Live Qwen profile `qwen-3.8-27B`: `base_url` now `/v1`, model `openai/qwen3.8:27b-q4_K_M`

## 06-test

- Unit: 21 passed (`tests/` including `test_workspace_session_forwards_to_agent_server`)
- Live: `POST /api/auth/workspace-session` → 204 (was 404); `/api/auth/me` still 200

## 07-review

**Status: PASS**

- Fix matches root cause; login/credits/infra still gateway-owned
- Residual: conversations started with the old Qwen model id still fail until a new chat is opened

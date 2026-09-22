# Task — Phase 7 line 122: Docker + LLM_BACKEND=self_hosted (196)

Workdir: agent-harness/dong

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] Docker + `LLM_BACKEND=self_hosted` (196).`

Do NOT implement lines 123–127 (smoke tay, eval run, judge, golden target) in this task.

## Goal

Docker stack (`docker compose up --build -d`) phải sẵn sàng chạy production demo với `LLM_BACKEND=self_hosted` trỏ gateway `192.168.1.196:18083` — người dùng chỉ cần copy `.env`, set DB secrets, và verify health + llm ping.

## Context

- `docker-compose.yml`: ai_backend dùng `env_file: .env` nhưng chưa khai báo rõ LLM vars trong `environment:`.
- `src/config.py`: defaults `MODEL_BASE_URL=http://192.168.1.196:18083/v1`, `MODEL_NAME=qwen3-4b`.
- `tests/test_api.py`: đã có docker compose structure tests.
- `specs/test-plan.md` Live Production: `curl /api/health` → ok + backend=self_hosted; `curl /api/llm/ping` → model qwen3-4b.
- `/api/health` trả `llm_backend` (không phải `backend`) — giữ nguyên field hiện có.

## Requirements

1. **docker-compose.yml** — ai_backend `environment:` bổ sung passthrough LLM self_hosted với default production:
   ```yaml
   LLM_BACKEND: ${LLM_BACKEND:-self_hosted}
   MODEL_BASE_URL: ${MODEL_BASE_URL:-http://192.168.1.196:18083/v1}
   MODEL_NAME: ${MODEL_NAME:-qwen3-4b}
   MODEL_API_KEY: ${MODEL_API_KEY:-}
   MODEL_ENDPOINT: ${MODEL_ENDPOINT:-http://192.168.1.196:18083/v1/chat/completions}
   ```
   - `.env` vẫn override được (OpenAI smoke: set `LLM_BACKEND=openai` trong `.env`).
   - Không đổi Langfuse / network config hiện có.

2. **`.env.example`** — thêm block comment rõ:
   - Production Docker mặc định `self_hosted` qua compose defaults.
   - OpenAI = override `LLM_BACKEND=openai` trong `.env`.
   - Liệt kê vars bắt buộc: `MODEL_API_KEY`, DB_* cho live demo.

3. **Script verify** — tạo `scripts/verify-docker-self-hosted.sh`:
   - Kiểm tra `curl -sf http://localhost:${BACKEND_PORT:-8000}/api/health` → parse `llm_backend` == `self_hosted`.
   - Kiểm tra `curl -sf http://localhost:${BACKEND_PORT:-8000}/api/llm/ping` → status ok (exit 0 nếu ping OK, exit 1 + message rõ nếu fail — dùng cho manual verify trên LAN 196).
   - Script bash, executable, không cần pytest.

4. **Tests** — tạo `tests/test_phase7_docker_self_hosted.py`:
   - Parse docker-compose.yml: ai_backend environment có `LLM_BACKEND`, `MODEL_BASE_URL` default self_hosted @ 196.
   - Mock/settings: khi `LLM_BACKEND=self_hosted`, `/api/health` trả `llm_backend=self_hosted`.
   - Mock llm ping: `/api/llm/ping` trả backend self_hosted + model qwen3-4b.
   - Không cần chạy Docker thật trong pytest.

5. **Docs**:
   - Mark `[x]` line 122 in `specs/implementation-plan.md`.
   - Add entry `specs/change-log.md`.

6. **Run**:
   ```bash
   pytest tests/test_phase7_docker_self_hosted.py tests/test_api.py -q -k "docker or self_hosted or dual_model"
   pytest -q
   ```

## Constraints

- Minimal diff — chỉ files cần cho task này.
- Không chạy eval golden-30, không chạy docker build thật (pytest offline).
- PEP 8.

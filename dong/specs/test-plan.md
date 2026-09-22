# Test Plan — dong v6

**Trạng thái:** Verify sau **từng task** (TNN) trong `implementation-plan.md` — không đợi hết phase.

## Offline (pytest)

```bash
cd agent-harness/dong
pytest -q
```

| Chủ đề | Kỳ vọng |
|--------|---------|
| **resource paths** | `DOCS_ROOT`, prompt dir → `resource/` |
| **Prompt registry** | render production; thiếu biến → ValueError |
| **LLM backend** | mock `openai` vs `self_hosted`; key rotation |
| **Structured schemas** | v5 schemas giữ hành vi |
| **QueryPlan** | validator, builder, repair |
| **Trace** | node input/output full; metadata session/user |
| **Memory short-term** | 2 turn cùng `session_id` nhớ context |
| **Memory long-term** | fact store + recall cùng `user_id`, session khác |
| **TTL cache** | hit trong 300s; miss sau expire (mock time) |
| **Chart** | bar + pie non-empty |
| **Multi-agent** | orchestrator route fire/anomaly mock |
| **Guardrail** | injection, out-of-scope |
| **Sessions API** | list/create/delete mock |
| **Docker spec** | compose valid; `resource/` in Dockerfile |

## Live — Production (Docker + LLM 196)

**Điều kiện:** `LLM_BACKEND=self_hosted`, gateway `192.168.1.196:18083`, DB read-only.

```bash
cd agent-harness/dong
docker compose up --build -d
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/llm/ping
```

| Case | Kỳ vọng |
|------|---------|
| Health | ok + backend=self_hosted |
| Ping 196 | model qwen3-4b (hoặc tên gateway) |
| Session UI | Tạo session mới; đổi session; lịch sử hiển thị |
| Short-term | "Tên tôi là A" → câu sau trong cùng session nhớ |
| Long-term | Fact → session mới + cùng user_id vẫn recall (nếu bật) |
| TTL | Cùng câu trong 5 phút → cache hit / latency thấp hơn |
| Số liệu | "Hôm nay có bao nhiêu lượt xe CAR vào?" |
| Fire #010 | "Có cảnh báo cháy khói hôm nay không?" |
| Anomaly #009 | "Có phát hiện leo trèo không?" |
| AIOC #015,#017 | "Làm sao thêm camera trên AIOC?" — keyword đủ |
| Chart bar | "Vẽ biểu đồ cột lượt xe theo loại hôm nay" |
| Chart pie | "Vẽ biểu đồ tròn tỷ lệ loại xe" |
| Langfuse | Mỗi node full input/output |
| SSE graph | Hover khớp Langfuse |

## Live — OpenAI smoke (optional)

Copy `OPENAI_API_KEYS` từ `llm-engineer-demo/.env` → `dong/.env` (không commit).

```bash
LLM_BACKEND=openai docker compose up -d
curl -s http://localhost:8000/api/llm/ping
# 1 câu how-to qua UI
```

## Golden 30 (Phase 9)

```bash
unset PYTEST_CURRENT_TEST
cd agent-harness/dong
python eval/run.py
python eval/run.py --judge
```

| Metric | Baseline (v5) | Target v6 |
|--------|---------------|-----------|
| Rule pass | 22/30 | **≥28/30** |
| Fail ưu tiên | 008–011, 015, 017, 023, 024 | pass |
| Output | `eval/results/golden-30.md` | `mode: live`, timestamp mới |
| Judge | 1–5 tiếng Việt | ≥3/5 trên case pass |

**Không** ghi đè báo cáo live bằng `--offline` trừ CI mock.

## Eval workflow (theo llm-engineer-demo)

1. Dataset YAML → agent thật (`run_agent` / stream).
2. Rule: `must_include`, `must_include_tool`, columns.
3. Optional `--judge`: LLM chấm 1–5.
4. Ghi markdown report + slice breakdown.

## Regression v5 → v6

| Giữ | Thay đổi |
|-----|----------|
| QueryPlan + read-only SQL | Prompt → `resource/prompts/` |
| Guardrail injection | Docs → `resource/docs/` |
| SSE live graph | + full I/O trace |
| Docker deploy | + memory + sessions UI |
| Langfuse | + session_id metadata |

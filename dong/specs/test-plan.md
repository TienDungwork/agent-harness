# Test Plan — dong v5

Người dùng / CI chạy sau từng phase. **Phase 1–7** xong; đạt trạng thái demo-ready.

## Offline (pytest)

```bash
cd agent-harness/dong
pytest -q
find tests -name 'test_*.py' | wc -l   # < 10
test ! -d backend
```

| Chủ đề | Kỳ vọng |
|--------|---------|
| **Structured LLM** | Mock `invoke_structured`; schema validate; lỗi parse → fallback rõ |
| **Rewrite** | Node rewrite output `RewrittenQuestion`; SSE có `node_id=rewrite` |
| **Intent** | Structured `IntentResult`; how-to ≠ query_data |
| **QueryPlan** | Plan → SQL parameterized; thêm filter → đúng WHERE |
| **Validator** | `DELETE`/`INSERT` reject; whitelist table |
| **Docs** | Retrieve YAML card; how-to không gọi DB |
| **Chart** | `render_chart` trả base64 non-empty với rows mẫu |
| **Guardrail** | injection 400; thời tiết out-of-scope |
| **Read-only** | SQL ghi bị chặn |
| **Trace/cache** | monitoring off = no-op; cache hit sau rewrite key |
| **API stream** | SSE thứ tự node; `parent_span` Langfuse mock |
| **Docker spec** | `docker-compose.yml` + `langfuse/docker-compose.yml` hợp lệ |

## Live (Docker — đường chính v5)

```bash
cd agent-harness/dong
cd langfuse && docker compose up -d  # tuỳ chọn
docker compose up --build -d
curl -s http://localhost:${BACKEND_PORT:-8000}/api/health
# Mở http://localhost:${FRONTEND_PORT:-8080}
```

| Case | Kỳ vọng |
|------|---------|
| Health | `status: ok`, model, `db_configured` |
| Ping LLM | `/api/llm/ping` → OK (LAN 196) |
| Graph | Node `rewrite` → … → `respond` / `answer_from_docs` |
| Chart | PNG hiển thị khi hỏi biểu đồ |
| Langfuse | Trace `chat` + nested spans; không filter ẩn |
| Hover I/O | Input/output từng node trên UI |

## Golden 30 (Phase 6)

```bash
# LIVE MODE (chạy thật, yêu cầu LAN 196 + DB, không set PYTEST_CURRENT_TEST)
# Thời gian chạy: ~15-30 phút.
python eval/run.py
python eval/run.py --judge

# OFFLINE MODE (dùng khi mock/CI, không phản ánh chất lượng product)
python eval/run.py --offline
```

- Dataset: `eval/datasets/agent_stat/v2.yaml` (30 câu).
- Output: `eval/results/golden-30.md` — `mode: live` (hoặc `offline`), cột pass/fail, latency, tool/plan, judge.
- Cần có kết nối DB và LLM LAN 196 cho live mode. Không ghi đè offline test (mock) lên kết quả live cũ (trừ khi dùng flag `--offline` trỏ output khác nếu muốn giữ).

## Regression v4 → v5

| Hành vi v4 | v5 |
|------------|-----|
| ReAct tool cố định | QueryPlan + builder |
| `docs/vms/*.md` grep | YAML cards duy |
| Không chart | PNG chart |
| Free-text classify | Structured |
| Không rewrite | Node rewrite |

Giữ: guardrail, SSE graph, cache, Langfuse stream path, read-only DB.

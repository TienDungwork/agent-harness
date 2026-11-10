# v17 Rich Langfuse + MinIO charts + no-dict-`.get` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.  
> **Spec:** [v17-langfuse-rich-trace-design.md](v17-langfuse-rich-trace-design.md)  
> **Repo root for commands:** `agent-harness/dong/` with `PYTHONPATH=.`  
> **Commits:** chỉ `git commit` khi user yêu cầu rõ (repo rule). Cursor plans/reviews; Antigravity implement nếu user nhờ `agy`.

**Goal:** Làm Langfuse parity UI (prompt redacted + slim state), lưu chart lên MinIO `chatbot-images/chatbot/` (TTL 10 ngày, SSE ưu tiên `chart_url`), và migrate hết dict `.get` trong `dong/src` theo rule no-dict-get.

**Architecture:** Helper `trace_payload` cho mọi I/O Langfuse; client MinIO S3-compatible upload sau `render_chart`; FE đọc URL public; migrate `.get` → `['key']` theo cụm package với pytest từng cụm.

**Tech Stack:** Python 3, Langfuse SDK (hiện có), `boto3` (S3 API MinIO), FastAPI SSE, pytest, frontend `app.js`.

## Global Constraints

- Không đổi topology LangGraph / tên node.
- Không đẩy PNG / full `rows` / full `events` lên Langfuse.
- Dict field access: `obj['key']` — **cấm** `dict.get` trong `src/` (rule `.cursor/rules/no-dict-get.mdc`).
- **Không** đổi `ContextVar.get()` / `Queue.get()` / `os.environ.get` / `os.getenv` — đó không phải dict field.
- MinIO bucket `chatbot-images`, prefix `chatbot/`, TTL 10 ngày; không dùng MinIO Langfuse `:9190`.
- SSE chart: ưu tiên `chart_url`; base64 chỉ khi upload fail.
- Specs SDD chỉ trong `agent-harness/dong/specs/`.
- Code mới trong Task A–B cũng phải dùng `['key']` (không tạo thêm `.get`).

## File map

| Path | Responsibility |
|------|----------------|
| `src/infra/monitoring/trace_payload.py` | `redact_text`, `slim_state`, `llm_io_payload` |
| `src/infra/monitoring/tracing.py` | giữ `trace_step` (consume payload từ caller) |
| `src/domain/agents/graph.py` | `_wrap_node`: gắn `state_snapshot`; SSE chart_url passthrough |
| `src/infra/llm/client.py` | `invoke_text` full prompt I/O |
| `src/infra/llm/structured.py` | generation span full I/O nếu đang length-only |
| `src/infra/storage/minio_charts.py` | upload PNG → public URL |
| `src/shared/settings/__init__.py` | MINIO_* / CHART_OBJECT_TTL_DAYS |
| `.env_sample` | keys mẫu (không value secret) |
| `src/domain/agents/nodes/render_chart.py` | upload sau render; set `chart_url` |
| `src/domain/agents/state.py` | optional field `chart_url: str` |
| `src/api/helpers/sse_helpers.py` | `build_chart_sse_event(..., chart_url=)` |
| `src/api/routers/routes_agent.py` | forward `chart_url` |
| `frontend/app.js` | `img src = chart_url` ưu tiên hơn data-URI |
| `requirements.txt` | thêm `boto3` |
| `tests/test_trace_payload.py` | unit redact/slim/llm_io |
| `tests/test_minio_charts.py` | unit upload mock |

---

### Task 1: `trace_payload` helper + tests

**Files:**
- Create: `src/infra/monitoring/trace_payload.py`
- Create: `tests/test_trace_payload.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `redact_text(text: str, *, max_chars: int = 32000) -> str`
  - `slim_state(state: Mapping[str, Any]) -> dict[str, Any]`
  - `llm_io_payload(system: str, user: str, text: str) -> dict` với keys `input`/`output`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_trace_payload.py
from src.infra.monitoring.trace_payload import llm_io_payload, redact_text, slim_state


def test_redact_masks_sk_and_bearer():
    s = redact_text("Bearer SECRETTOKEN123 and sk-abcdef0123456789xyz")
    assert "SECRETTOKEN123" not in s
    assert "sk-abcdef0123456789xyz" not in s
    assert "Bearer" in s or "***" in s


def test_redact_truncates():
    s = redact_text("x" * 100, max_chars=20)
    assert s.endswith("…[truncated]")
    assert len(s) < 40


def test_slim_state_drops_heavy_fields():
    snap = slim_state({
        "question": "q",
        "intent": "query_data",
        "sql": "SELECT 1",
        "error": "",
        "repair_count": 0,
        "rows": [{"a": 1}],
        "events": [{"node_id": "x"}],
        "chart_png_base64": "aaa",
        "messages": [],
        "schema_excerpt": "CREATE TABLE...",
        "orchestrator_step_index": 1,
        "respond_mode": "stat",
        "selected_tables": ["plate_event"],
    })
    assert snap["question"] == "q"
    assert snap["row_count"] == 1
    assert "rows" not in snap
    assert "events" not in snap
    assert "chart_png_base64" not in snap
    assert "schema_excerpt" not in snap


def test_llm_io_payload_has_full_text_not_lens():
    p = llm_io_payload("sys", "usr", "out")
    assert p["input"]["system"] == "sys"
    assert p["input"]["user"] == "usr"
    assert p["output"]["text"] == "out"
    assert "system_len" not in p["input"]
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```bash
cd agent-harness/dong && PYTHONPATH=. pytest tests/test_trace_payload.py -q
```

Expected: `ImportError` / collection error

- [ ] **Step 3: Implement `trace_payload.py`**

```python
"""Langfuse-safe payload helpers: redact, slim state, LLM I/O."""

from __future__ import annotations

import re
from typing import Any, Mapping

def redact_text(text: str, *, max_chars: int = 32000) -> str:
    if not isinstance(text, str):
        text = str(text)
    out = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}", "Bearer ***", text)
    out = re.sub(r"sk-[A-Za-z0-9]{16,}", "sk-***", out)
    out = re.sub(r"(?i)password\s*[=:]\s*\S+", "password=***", out)
    if len(out) > max_chars:
        return out[:max_chars] + "…[truncated]"
    return out


def slim_state(state: Mapping[str, Any]) -> dict[str, Any]:
    rows = state["rows"] if "rows" in state and isinstance(state["rows"], list) else []
    snap: dict[str, Any] = {"row_count": len(rows)}
    for key in (
        "question",
        "intent",
        "sql",
        "error",
        "repair_count",
        "orchestrator_step_index",
        "respond_mode",
        "selected_tables",
    ):
        if key in state:
            snap[key] = state[key]
    return snap


def llm_io_payload(system: str, user: str, text: str) -> dict[str, Any]:
    return {
        "input": {
            "system": redact_text(system or ""),
            "user": redact_text(user or ""),
        },
        "output": {"text": redact_text(text or "")},
    }
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
PYTHONPATH=. pytest tests/test_trace_payload.py -q
```

Expected: `4 passed`

- [ ] **Step 5:** Commit chỉ khi user yêu cầu.

---

### Task 2: Wire Langfuse — `_wrap_node` + `invoke_text`

**Files:**
- Modify: `src/domain/agents/graph.py` (`_wrap_node`)
- Modify: `src/infra/llm/client.py` (`invoke_text`)
- Modify: `src/infra/llm/structured.py` (nếu span chỉ ghi length)
- Test: extend `tests/test_trace_payload.py` hoặc `tests/test_product_observability_errors.py` với mock span

**Interfaces:**
- Consumes: `slim_state`, `llm_io_payload` từ Task 1
- Produces: node metadata có `state_snapshot`; LLM box input/output full text

- [ ] **Step 1: Failing test — mock `invoke_text` writes full prompts**

Trong test: monkeypatch `trace_step` capture box; gọi `invoke_text` với fake llm; assert `"system_len" not in` captured input và `"system" in` captured input.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Update `invoke_text`**

```python
from src.infra.monitoring.trace_payload import llm_io_payload

# inside substep branch after text returned:
payload = llm_io_payload(system_prompt or "", user_prompt or "", text)
box["input"] = payload["input"]  # if _finish_step uses box; else pass input= at start
box["output"] = payload["output"]
```

At `trace_step(..., input=...)`: pass `llm_io_payload(...)["input"]` **before** call only if prompts known (yes); set `box["output"]` after.

Replace length-only `trace_in` / `text_len`.

- [ ] **Step 4: Update `_wrap_node`**

Sau khi có `meta` từ event (hoặc empty meta):

```python
from src.infra.monitoring.trace_payload import slim_state

meta["state_snapshot"] = slim_state(state)
step["metadata"] = json_safe(meta)
```

Dùng `['key']` cho field bắt buộc đã có trên state khi đọc trong wrapper mới; optional → `'k' in state`.

- [ ] **Step 5: structured.py** — cùng pattern nếu đang log length-only.

- [ ] **Step 6:**

```bash
PYTHONPATH=. pytest tests/test_trace_payload.py tests/test_product_observability_errors.py -q
```

Expected: pass (fix failures unrelated → báo user)

---

### Task 3: MinIO settings + `minio_charts` client

**Files:**
- Modify: `src/shared/settings/__init__.py`
- Modify: `.env_sample`
- Modify: `requirements.txt` — add `boto3>=1.34`
- Create: `src/infra/storage/__init__.py`
- Create: `src/infra/storage/minio_charts.py`
- Create: `tests/test_minio_charts.py`

**Interfaces:**
- Consumes: settings MINIO_*
- Produces: `upload_chart_png(png_bytes: bytes, *, session_id: str) -> str` (public URL)  
  raises on failure (caller fallback)

- [ ] **Step 1: Add settings fields**

```python
minio_endpoint: str = Field(default="", alias="MINIO_ENDPOINT")
minio_access_key: str = Field(default="", alias="MINIO_ACCESS_KEY")
minio_secret_key: str = Field(default="", alias="MINIO_SECRET_KEY")
minio_bucket: str = Field(default="chatbot-images", alias="MINIO_BUCKET")
minio_chart_prefix: str = Field(default="chatbot", alias="MINIO_CHART_PREFIX")
minio_public_base_url: str = Field(default="", alias="MINIO_PUBLIC_BASE_URL")
chart_object_ttl_days: int = Field(default=10, alias="CHART_OBJECT_TTL_DAYS")
```

`.env_sample`:

```text
MINIO_ENDPOINT=
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=chatbot-images
MINIO_CHART_PREFIX=chatbot
MINIO_PUBLIC_BASE_URL=
CHART_OBJECT_TTL_DAYS=10
```

- [ ] **Step 2: Failing test with mock boto3 client**

```python
def test_upload_chart_png_builds_chatbot_key(monkeypatch):
    # mock boto3.client put_object; assert Key startswith "chatbot/"
    # assert returned URL contains bucket and key
    ...
```

- [ ] **Step 3: Implement**

```python
# src/infra/storage/minio_charts.py
"""Upload agent chart PNGs to MinIO (chatbot-images/chatbot/)."""

from __future__ import annotations

import uuid
from urllib.parse import urljoin

import boto3
from botocore.client import Config

from src.shared.config import settings


def upload_chart_png(png_bytes: bytes, *, session_id: str) -> str:
    if not settings.minio_endpoint or not settings.minio_access_key:
        raise RuntimeError("MinIO not configured")
    prefix = settings.minio_chart_prefix.strip("/")
    key = f"{prefix}/{session_id or 'default'}/{uuid.uuid4().hex}.png"
    client = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    client.put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    base = (settings.minio_public_base_url or settings.minio_endpoint).rstrip("/")
    return f"{base}/{settings.minio_bucket}/{key}"
```

- [ ] **Step 4:** `pip install boto3` trong env/Docker; thêm `requirements.txt`

- [ ] **Step 5:**

```bash
PYTHONPATH=. pytest tests/test_minio_charts.py -q
```

Expected: pass

- [ ] **Step 6: Lifecycle 10 ngày (ops, document in change-log)**

Console MinIO hoặc:

```bash
mc ilm rule add myminio/chatbot-images --prefix "chatbot/" --expire-days 10
```

Bucket policy: public-read **prefix** `chatbot/` (ops). Ghi bước vào `specs/change-log.md` khi implement.

---

### Task 4: Wire chart upload → SSE + FE

**Files:**
- Modify: `src/domain/agents/state.py` — `chart_url: str`
- Modify: `src/domain/agents/nodes/render_chart.py`
- Modify: `src/domain/agents/nodes/io.py` — allow `chart_url` on events
- Modify: `src/api/helpers/sse_helpers.py` — `build_chart_sse_event(..., chart_url=None)`
- Modify: `src/api/routers/routes_agent.py` — pass `chart_url`
- Modify: `src/domain/agents/graph.py` — `q.put` include `chart_url`
- Modify: `frontend/app.js` — prefer `chartObj.url`

**Interfaces:**
- Consumes: `upload_chart_png`
- Produces: SSE fields `chart_url` and optionally empty `chart_png_base64` on success

- [ ] **Step 1: Update `build_chart_sse_event`**

```python
def build_chart_sse_event(
    chart_spec: dict[str, Any] | None,
    chart_png_base64: str | None,
    chart_rows: list[dict] | None = None,
    chart_url: str | None = None,
) -> dict[str, Any]:
    ...
    if chart_url:
        event["chart_url"] = chart_url
        event["chart_png_base64"] = ""
    else:
        event["chart_png_base64"] = chart_png_base64 or ""
```

- [ ] **Step 2: In `render_chart_node` after `png_base64`**

```python
import base64
from src.infra.storage.minio_charts import upload_chart_png

chart_url = ""
png_for_sse = png_base64 or ""
if png_base64:
    try:
        chart_url = upload_chart_png(
            base64.b64decode(png_base64),
            session_id=session_id,
        )
        png_for_sse = ""  # success → URL only
    except Exception:
        chart_url = ""
        png_for_sse = png_base64
# state + node_event: chart_url, chart_png_base64=png_for_sse
```

- [ ] **Step 3: `routes_agent` / `_wrap_node`** forward `chart_url` like `chart_png_base64`.

- [ ] **Step 4: FE `app.js`**

Where chart renders:

```javascript
const chartUrl = chartObj.url || chartObj.chart_url || null;
...
} else if (chartUrl) {
  chartSlot.innerHTML = `<img src="${chartUrl}" alt="Biểu đồ" style="max-width:100%; border-radius:8px; display:block; margin:0 auto;">`;
} else if (chartPng) {
  chartSlot.innerHTML = `<img src="data:image/png;base64,${chartPng}" ...>`;
}
```

Map SSE `chart_url` into `lastChart` / chart payload object `{ url, png, spec, rows }`.

- [ ] **Step 5: Manual smoke** — hỏi biểu đồ trên UI; Network/SSE có `chart_url`; `<img src="http://…/chatbot-images/chatbot/...">` load được. Tắt MinIO credential → vẫn thấy base64.

---

### Task 5: Migrate dict `.get` — `infra/` + `shared/`

**Files:** mọi `src/infra/**/*.py`, `src/shared/**/*.py` có dict `.get` (trừ ngoại lệ Global Constraints)

**Interfaces:** none mới — semantics giữ optional qua `'k' in d`

- [ ] **Step 1: Inventory**

```bash
cd agent-harness/dong && rg -n '\.get\(' src/infra src/shared --glob '*.py'
```

- [ ] **Step 2: Replace theo pattern**

```python
# before
x = d.get("k", "")
# after (required)
x = d["k"]
# after (optional string default)
x = d["k"] if "k" in d else ""
```

Không đụng `os.environ.get`, ContextVar/Queue `.get`.

- [ ] **Step 3:**

```bash
PYTHONPATH=. pytest tests/test_product_observability_errors.py tests/test_product_memory_cache.py tests/test_minio_charts.py tests/test_trace_payload.py -q
```

- [ ] **Step 4: Grep gate infra/shared** — không còn dict `.get` trái phép.

---

### Task 6: Migrate dict `.get` — `domain/`

**Files:** `src/domain/**/*.py`

- [ ] **Step 1:** `rg '\.get\(' src/domain -g '*.py'`
- [ ] **Step 2:** Migrate file-by-file; ưu tiên `nodes/`, `graph.py`, sql/docs tools.
- [ ] **Step 3:**

```bash
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py tests/test_product_sql_agent.py tests/test_product_chart_visualization.py tests/test_inline_respond.py -q
```

Expected: pass hoặc báo failure thật

---

### Task 7: Migrate dict `.get` — `api/` + `application/` + `main.py`

**Files:** `src/api/**`, `src/application/**`, `src/main.py`

- [ ] **Step 1–2:** inventory + migrate (SSE helpers, routes_agent, agent_turn).
- [ ] **Step 3:**

```bash
PYTHONPATH=. pytest tests/test_product_api_gateway.py tests/test_product_router_ttl_cache.py -q
```

- [ ] **Step 4: Final grep gate**

```bash
rg -n '\.get\(' src --glob '*.py' | rg -v 'environ\.get|getenv|ContextVar|queue\.|Queue|\.get\(\)' 
# thủ công loại method không phải dict; mục tiêu: 0 dict-field .get
```

- [ ] **Step 5: Update `specs/change-log.md` + `specs/README.md` status v17 done khi AC xanh.**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| AC-1..5 Langfuse | 1–2 |
| AC-6..8 MinIO | 3–4 |
| AC-9 no `.get` | 5–7 |
| Helper approach 2 | 1 |
| chart_url fallback C | 4 |
| Lifecycle 10d | 3 step 6 |
| Rule no-dict-get | 5–7 + already in `.cursor/rules` |

## Placeholder / consistency self-review

- Signatures ổn định: `slim_state`, `llm_io_payload`, `upload_chart_png`, `build_chart_sse_event(..., chart_url=)`.
- Không TBD trong steps trên.
- `ContextVar.get` excluded explicitly.

# v15 Leaf agents + flat graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.  
> **Spec:** [v15-leaf-agents-flat-graph-design.md](v15-leaf-agents-flat-graph-design.md) · **AC:** product-spec AC-11.  
> **Repo root for commands:** `agent-harness/dong/` with `PYTHONPATH=.`  
> **Commits:** chỉ `git commit` khi user yêu cầu rõ (repo rule).

**Goal:** Đóng gói `sql_agent` / `docs_agent` kiểu leaf `ai_backend`, gộp `vms/core` vào `vms/graph.py` (wire flat), không đổi hành vi / tên node / HTTP / SSE.

**Architecture:** Move-only. Leaf packages chỉ export node callables + tools; mọi `add_node`/`add_edge` ở `vms/graph.py`. Không `StateGraph.compile()` trong leaf. Không `chart_agent`.

**Tech Stack:** Python 3, LangGraph, pytest, FastAPI (không đổi).

## Global Constraints

- Không đổi body logic trong node/tools (chỉ đổi import path / vị trí file).
- Không `compile()` trong `sql_agent` / `docs_agent`.
- Giữ symbol trên `src.domain.agents.vms.graph`: `_build_graph`, `_get_graph`, `reset_graph`, `run_agent`, `run_agent_stream`, `_wrap_node`, `_stream_queue`, `emit_answer_chunks`.
- Giữ tên node LangGraph hiện tại (guardrail_input, recall, rewrite, classify, …).
- Không tạo `chart_agent/`; `render_chart_node` → `vms/nodes/render_chart.py`.
- Specs SDD chỉ trong `agent-harness/dong/specs/`.

## File map (khóa decomposition)

| Path | Responsibility |
|------|----------------|
| `src/domain/agents/vms/graph.py` | Build flat graph + run/stream + wrap/SSE (gộp từ `core/`) |
| `src/domain/agents/vms/state.py` | AgentState / I/O types (không đổi) |
| `src/domain/agents/vms/nodes/*` | Guardrail, memory, rewrite/classify, respond, render_chart, io |
| `src/domain/agents/vms/tools.py` | Helpers: strip_thinking, memory_context, chart_fallback, … |
| `src/domain/agents/sql_agent/graph.py` | Re-export SQL-related **node** entrypoints |
| `src/domain/agents/sql_agent/tools.py` | generate/validate/execute/batch/pre_sql/scope modules |
| `src/domain/agents/sql_agent/state.py` | `from vms.state import AgentState` |
| `src/domain/agents/docs_agent/graph.py` | Re-export docs **node** entrypoints |
| `src/domain/agents/docs_agent/tools.py` | docs adapter + camera_registry |
| `src/domain/agents/docs_agent/state.py` | re-export AgentState |
| `src/domain/agents/multi_agent/*` | Không đổi logic |

**Xóa khi xong:** `vms/core/`, `vms/sql/`, `vms/routing/`, `vms/respond/`, `vms/adapters/`, và `vms/nodes/pipeline.py` sau khi tách.

---

### Task 1: Baseline lock (node names)

**Files:**
- Test (read-only): `tests/test_product_graph_orchestrator.py` (`test_graph_nodes_and_structure`)

**Interfaces:**
- Consumes: current `vms.core.wiring._build_graph`
- Produces: evidence baseline PASS trước migrate

- [ ] **Step 1: Chạy baseline**

```bash
cd agent-harness/dong && PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure -q
```

Expected: `1 passed`

- [ ] **Step 2: Ghi note** — nếu fail pre-existing, dừng và báo user (không bắt đầu move).

---

### Task 2: Tạo `sql_agent` + move `vms/sql`

**Files:**
- Create: `src/domain/agents/sql_agent/__init__.py`
- Create: `src/domain/agents/sql_agent/state.py`
- Create: `src/domain/agents/sql_agent/tools/` (package) — move các file từ `vms/sql/`
- Create: `src/domain/agents/sql_agent/graph.py`
- Modify: mọi import `src.domain.agents.vms.sql` → `src.domain.agents.sql_agent.tools` (hoặc `sql_agent.graph` cho node)

**Interfaces:**
- Consumes: existing `generate_sql_node`, `validate_sql_node`, `repair_sql_node`, `execute_sql_node` từ `vms/sql/*.py`
- Produces: same callables at `sql_agent.tools.generate.generate_sql_node` etc.; `sql_agent.graph` re-exports nodes + later `retrieve_schema_node`

- [ ] **Step 1: Skeleton**

```bash
mkdir -p src/domain/agents/sql_agent/tools
```

`sql_agent/__init__.py`:

```python
"""SQL leaf agent — tools + node entrypoints; graph wire ở vms.graph (flat)."""
```

`sql_agent/state.py`:

```python
"""Re-export shared AgentState (một state cho flat graph)."""
from src.domain.agents.vms.state import AgentState, Agent_Input, Agent_Output

__all__ = ["AgentState", "Agent_Input", "Agent_Output"]
```

- [ ] **Step 2: Move sql modules**

```bash
git mv src/domain/agents/vms/sql/generate.py src/domain/agents/sql_agent/tools/generate.py
git mv src/domain/agents/vms/sql/validate.py src/domain/agents/sql_agent/tools/validate.py
git mv src/domain/agents/vms/sql/execute.py src/domain/agents/sql_agent/tools/execute.py
git mv src/domain/agents/vms/sql/batch.py src/domain/agents/sql_agent/tools/batch.py
git mv src/domain/agents/vms/sql/pre_sql.py src/domain/agents/sql_agent/tools/pre_sql.py
git mv src/domain/agents/vms/sql/scope.py src/domain/agents/sql_agent/tools/scope.py
# nếu không dùng git mv: mv tương đương
printf '%s\n' '"""SQL tool modules (generate/validate/execute/…)."""' > src/domain/agents/sql_agent/tools/__init__.py
rm -rf src/domain/agents/vms/sql
```

- [ ] **Step 3: `sql_agent/graph.py` (no compile)**

```python
"""Node entrypoints for SQL path — do not compile a subgraph."""
from src.domain.agents.sql_agent.tools.execute import execute_sql_node
from src.domain.agents.sql_agent.tools.generate import generate_sql_node
from src.domain.agents.sql_agent.tools.validate import repair_sql_node, validate_sql_node

__all__ = [
    "generate_sql_node",
    "validate_sql_node",
    "repair_sql_node",
    "execute_sql_node",
]
```

- [ ] **Step 4: Bulk rewrite imports**

```bash
# từ agent-harness/dong
rg -l 'src\.domain\.agents\.vms\.sql' -g '*.py' | while read -r f; do
  sed -i 's/src\.domain\.agents\.vms\.sql/src.domain.agents.sql_agent.tools/g' "$f"
done
```

Sửa `vms/core/wiring.py` (hoặc `vms/graph.py` nếu đã gộp) import node từ `sql_agent.graph`.

- [ ] **Step 5: Verify**

```bash
PYTHONPATH=. python -c "from src.domain.agents.sql_agent.graph import generate_sql_node, execute_sql_node; print('sql_agent ok')"
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure -q
```

Expected: import ok; `1 passed`

---

### Task 3: Tạo `docs_agent` + tách docs khỏi `pipeline.py`

**Files:**
- Create: `src/domain/agents/docs_agent/{__init__,state,graph}.py`
- Create: `src/domain/agents/docs_agent/tools/docs.py` (from `vms/adapters/docs.py`)
- Create: `src/domain/agents/docs_agent/tools/camera_registry.py` (from adapters)
- Create: `src/domain/agents/docs_agent/nodes.py` — chứa `retrieve_docs_node`, `answer_from_docs_node` từ `pipeline.py` (copy body không sửa logic)
- Create: `src/domain/agents/vms/nodes/render_chart.py` — `render_chart_node` + `_pad_direction_rows` nếu chỉ chart dùng
- Create: `src/domain/agents/sql_agent` thêm `retrieve_schema_node` (từ pipeline) vào `graph.py` / module `sql_agent/nodes.py` hoặc `tools/schema.py`
- Delete: `vms/nodes/pipeline.py`, `vms/adapters/` sau khi chuyển

**Interfaces:**
- Consumes: current functions in `vms/nodes/pipeline.py`
- Produces:
  - `docs_agent.graph.retrieve_docs_node`, `answer_from_docs_node`
  - `sql_agent.graph.retrieve_schema_node` (sau khi thêm)
  - `vms.nodes.render_chart.render_chart_node`

- [ ] **Step 1: Skeleton docs_agent** — giống Task 2 (`state` re-export `AgentState`).

- [ ] **Step 2: Move adapters → `docs_agent/tools/`**

```bash
mkdir -p src/domain/agents/docs_agent/tools
git mv src/domain/agents/vms/adapters/docs.py src/domain/agents/docs_agent/tools/docs.py
git mv src/domain/agents/vms/adapters/camera_registry.py src/domain/agents/docs_agent/tools/camera_registry.py
printf '%s\n' '"""Docs/camera tools."""' > src/domain/agents/docs_agent/tools/__init__.py
rm -rf src/domain/agents/vms/adapters
```

Sửa import trong file vừa move: `vms.adapters` → `docs_agent.tools`.

- [ ] **Step 3: Tách `pipeline.py`**

1. Copy `retrieve_docs_node` + `answer_from_docs_node` → `docs_agent/nodes.py` (giữ nguyên body; sửa import nội bộ).
2. Copy `retrieve_schema_node` → `sql_agent/tools/schema.py` hoặc `sql_agent/nodes.py`.
3. Copy `render_chart_node` (+ helper pad rows nếu thuộc chart) → `vms/nodes/render_chart.py`.
4. Cập nhật `docs_agent/graph.py`:

```python
"""Docs node entrypoints — do not compile a subgraph."""
from src.domain.agents.docs_agent.nodes import answer_from_docs_node, retrieve_docs_node

__all__ = ["retrieve_docs_node", "answer_from_docs_node"]
```

5. Cập nhật `sql_agent/graph.py` thêm `retrieve_schema_node`.
6. Xóa `vms/nodes/pipeline.py`; sửa mọi import `pipeline` → đích mới.

- [ ] **Step 4: Verify**

```bash
PYTHONPATH=. python -c "from src.domain.agents.docs_agent.graph import retrieve_docs_node; from src.domain.agents.vms.nodes.render_chart import render_chart_node; print('docs/chart ok')"
PYTHONPATH=. pytest tests/test_camera_registry.py::test_load_camera_registry_success tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure -q
```

Expected: `2 passed` (hoặc 3 nếu thêm fallback test)

---

### Task 4: Gộp `vms/core` → `vms/graph.py` + `vms/tools.py`

**Files:**
- Modify: `src/domain/agents/vms/graph.py` — thay facade re-export bằng nội dung thật từ `core/wiring.py`, `core/run.py`, `core/runtime.py`
- Create: `src/domain/agents/vms/tools.py` — từ `core/helpers.py` (+ sau này chart_fallback)
- Delete: `src/domain/agents/vms/core/`
- Modify: imports trong nodes/multi_agent trỏ `vms.core.helpers` → `vms.tools`

**Interfaces:**
- Consumes: symbols listed in Global Constraints
- Produces: same symbols on `src.domain.agents.vms.graph` and helpers on `vms.tools`

- [ ] **Step 1: Tạo `vms/tools.py`**

Copy nguyên `core/helpers.py` → `vms/tools.py` (đổi docstring module một dòng). Grep/replace `vms.core.helpers` → `vms.tools`.

- [ ] **Step 2: Gộp graph**

Thứ tự trong `vms/graph.py` (một file, section rõ):

1. runtime: `_stream_queue`, `emit_answer_chunks`, `_wrap_node`, …
2. wiring: `_build_graph`, `reset_graph`, `_get_graph`, `_compiled`
3. run: `_fresh_invoke_state`, `run_agent`, `run_agent_stream`, `save_graph_visualization`
4. `__all__` giữ API cũ

Import node từ:

- `vms.nodes.*`
- `sql_agent.graph`
- `docs_agent.graph`
- `multi_agent.*`

**Không** đổi chuỗi edge/conditional trong `_build_graph`.

- [ ] **Step 3: Xóa `vms/core/`** và grep sạch `vms.core`.

```bash
rg 'vms\.core' -g '*.py' agent-harness/dong
```

Expected: no matches (trừ change-log nếu có)

- [ ] **Step 4: Verify**

```bash
PYTHONPATH=. python -c "from src.domain.agents.vms.graph import run_agent, _build_graph, _wrap_node; from src.domain.agents.graph import run_agent as r2; assert run_agent is r2; print('graph ok')"
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure tests/test_product_graph_orchestrator.py::test_greeting_offline_fast_path_run_agent -q
```

Expected: PASS

---

### Task 5: Gom `routing` / `respond` vào `vms/nodes` + `vms/tools`

**Files:**
- Modify: `vms/nodes/rewrite_classify.py` — import từ modules chuyển vào `vms/nodes/` hoặc gộp file
- Move: `vms/routing/{rewrite,intent,inline_respond}.py` → `vms/nodes/` (hoặc `vms/nodes/routing_*.py`)
- Move: `vms/respond/simple_answer.py` → dùng bởi `vms/nodes/respond.py` (cùng package nodes hoặc `vms/tools`)
- Move: `vms/respond/chart_fallback.py` → `vms/tools` (append hoặc `from` trong tools)
- Delete: `vms/routing/`, `vms/respond/`

**Interfaces:**
- Produces: same function names (`rewrite_question`, `classify_intent`, …) tại path mới; cập nhật `__init__.py` agents nếu export

- [ ] **Step 1: Move files + sed import `vms.routing` / `vms.respond`**

- [ ] **Step 2: Verify offline rewrite/classify**

```bash
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py::test_rewrite_question_mock_structured tests/test_product_graph_orchestrator.py::test_classify_intent_offline_heuristics -q
```

Expected: PASS

---

### Task 6: Rewire toàn repo + dọn package

**Files:**
- Modify: mọi `.py` còn path cũ (tests + src)
- Modify: `src/domain/agents/__init__.py` exports
- Modify: `src/README.md`
- Modify: `specs/change-log.md`, tick `implementation-plan.md` 15.2–15.5

- [ ] **Step 1: Grep gate**

```bash
rg 'vms\.(sql|core|routing|respond|adapters)|nodes\.pipeline' -g '*.py' src tests || true
```

Expected: empty (no hits)

- [ ] **Step 2: Pytest subset AC-11**

```bash
PYTHONPATH=. pytest \
  tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure \
  tests/test_product_graph_orchestrator.py::test_greeting_offline_fast_path_run_agent \
  tests/test_product_graph_orchestrator.py::test_greeting_offline_fast_path_graph_events \
  tests/test_camera_registry.py \
  tests/test_product_observability_errors.py::test_v13_nested_trace_guardrail_recall_rewrite \
  tests/test_product_observability_errors.py::test_v13_execute_sql_batch_nested_postgres_query \
  -q
```

Expected: all passed (ghi fail pre-existing vào change-log nếu có)

- [ ] **Step 3: Docs** — cập nhật cây trong `src/README.md` theo design v15; change-log entry “v15 code”.

- [ ] **Step 4: Tick checkboxes** trong `specs/implementation-plan.md` phase 15.2–15.5.

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Target tree sql_agent / docs_agent / flat vms.graph | 2, 3, 4 |
| No chart_agent; render_chart in vms.nodes | 3 |
| No compile in leaf | 2, 3 (`graph.py` re-export only) |
| Node names / edges unchanged | 1, 4 (copy wiring) |
| Delete vms/core, sql, routing, respond, adapters | 2–5 |
| Pytest subset AC-11 | 6 |
| multi_agent untouched logic | — no task edits logic |

No TBD placeholders in steps above.

---

## Execution handoff

Plan saved to `agent-harness/dong/specs/v15-leaf-agents-flat-graph-plan.md`.

**Hai cách chạy:**

1. **Subagent-Driven (khuyến nghị)** — mỗi task một subagent, review giữa các task  
2. **Inline Execution** — làm tuần tự trong session này (executing-plans)

Bạn chọn **1** hay **2**?

# v16 Hierarchical agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.  
> **Spec:** [v16-hierarchical-agents-design.md](v16-hierarchical-agents-design.md)  
> **Repo root for commands:** `agent-harness/dong/` with `PYTHONPATH=.`  
> **Commits:** chỉ `git commit` khi user yêu cầu rõ. Message: `beta v0.x.y: …` (không conventional commits).  
> **Một task / lần** theo `AGENTS.md` — không nhảy phase.

**Goal:** Hierarchical LangGraph: root `build_graph`/`start_graph` + `analytics_team` | `knowledge_team` + `AgentTurnService` (SSE mới), tái dùng logic node v15.

**Architecture:** Shared prefix → `top_supervisor` ⇄ compiled team subgraphs → root `synth`. SQL repair chỉ trong analytics. Multi loop nâng từ `orchestrator_collect` lên root. Không ReAct worker trong v16.

**Tech Stack:** Python 3, LangGraph `StateGraph`, FastAPI, pytest, existing LLM/DB/memory infra.

## Global Constraints

- Không ReAct trong `sql_agent` / `docs_agent` (deterministic nodes).
- Không copy scan HITL / portfolio từ swarm.
- SQL repair loop chỉ trong `analytics/`; multi loop chỉ qua `top_supervisor`.
- Greeting / out_of_scope: classify → supervisor → `synth` (không vào team).
- Phase 1–5: HTTP/SSE cũ vẫn chạy qua `vms.graph` (strangler) cho đến Task 6 cắt sang service.
- Phase 6: SSE contract mới + cập nhật FE cùng task.
- Specs SDD chỉ trong `dong/specs/`.
- Mỗi task xong: đánh `[x]`, ghi `change-log.md`, giải thích cách test.

## File map (khóa decomposition)

| Path | Responsibility |
|------|----------------|
| `src/domain/agents/state.py` | `AssistantState` + re-export I/O nếu cần |
| `src/domain/agents/nodes.py` | `top_supervisor_node`, `route_from_top`, `synth_node` |
| `src/domain/agents/graph.py` | Root `build_graph`, `start_graph`, checkpointer; **không** còn shim-only |
| `src/domain/agents/analytics/state.py` | `AnalyticsTeamState` |
| `src/domain/agents/analytics/graph.py` | `build_analytics_graph()` → compiled subgraph |
| `src/domain/agents/analytics/nodes.py` | Entry/route trong analytics |
| `src/domain/agents/analytics/sql_agent/` | Move/keep từ `sql_agent/` (tools + node entrypoints) |
| `src/domain/agents/knowledge/state.py` | `KnowledgeTeamState` |
| `src/domain/agents/knowledge/graph.py` | `build_knowledge_graph()` |
| `src/domain/agents/knowledge/nodes.py` | Entry docs path |
| `src/domain/agents/knowledge/docs_agent/` | Move/keep từ `docs_agent/` |
| `src/application/agent_turn.py` | `AgentTurnService` + cache helpers |
| `src/api/routers/routes_agent.py` | Mỏng: gọi service |
| `src/domain/agents/vms/graph.py` | Giữ đến Task 6–7; rồi xóa hoặc thin re-export tạm |

**Xóa khi Task 7 xong:** shim thừa, cây trùng `agents/nodes|sql|routing|orchestrator|core/` (nếu còn), flat wiring chỉ sống trong `vms/` sau khi logic đã chuyển.

---

### Task 1: Skeleton state + root graph stub (strangler)

**Files:**
- Create/Replace: `src/domain/agents/state.py`
- Create: `src/domain/agents/nodes.py` (stubs)
- Replace: `src/domain/agents/graph.py` (thật, tạm ủy quyền `vms.graph`)
- Create: `tests/test_v16_hierarchy_skeleton.py`
- Modify: `specs/implementation-plan.md` (thêm block v16 Task 1), `specs/change-log.md`

**Interfaces:**
- Consumes: `vms.graph._build_graph`, `Agent_Output` từ `vms.state`
- Produces:
  - `class AssistantState(TypedDict, total=False)` với ít nhất: `messages`, `user_id`, `session_id`, `question`, `rewritten`, `intent`, `recalled_memories`, `next_team`, `step_results`, `final_answer`
  - `def build_graph()` → compiled graph (stub: vẫn flat vms bên trong **hoặc** wrapper compile `AssistantState` 1 node gọi vms — chọn **re-export compile từ vms** ở task này để zero behavior change)
  - `async def start_graph(question: str, request_deps: dict, *, user_id: str, session_id: str, request_id: str)` → `AsyncIterator[tuple[str, Any]]` stub chưa dùng ở API

- [x] **Step 1: Write failing test**

```python
# tests/test_v16_hierarchy_skeleton.py
from src.domain.agents.graph import build_graph
from src.domain.agents.state import AssistantState

def test_assistant_state_has_root_fields():
    keys = set(AssistantState.__annotations__)
    for k in ("question", "user_id", "session_id", "intent", "next_team", "final_answer"):
        assert k in keys

def test_build_graph_callable():
    g = build_graph()
    assert g is not None
```

- [x] **Step 2: Run test — expect FAIL**

```bash
cd agent-harness/dong && PYTHONPATH=. pytest tests/test_v16_hierarchy_skeleton.py -q
```

Expected: FAIL (import / missing symbols)

- [x] **Step 3: Implement minimal**

`state.py` — định nghĩa `AssistantState` (TypedDict). Có thể `from src.domain.agents.vms.state import Agent_Input, Agent_Output` re-export để tương thích.

`nodes.py`:

```python
def top_supervisor_node(state: AssistantState) -> dict:
    return {"next_team": "synth"}  # stub

def route_from_top(state: AssistantState) -> str:
    return state.get("next_team") or "synth"

def synth_node(state: AssistantState) -> dict:
    return {}
```

`graph.py`:

```python
"""Root agent graph — v16. Task 1: stub build_graph → vms flat compile."""
from src.domain.agents.vms.graph import _build_graph as build_graph

__all__ = ["build_graph"]
```

(Tách `start_graph` async stub optional; nếu thêm thì yield chưa bắt buộc wire API.)

- [x] **Step 4: Run test — expect PASS**

```bash
PYTHONPATH=. pytest tests/test_v16_hierarchy_skeleton.py -q
```

Expected: PASS

- [x] **Step 5: Docs** — `[x]` Task 1 trong plan này + `change-log.md` block ngày. Commit **chỉ nếu user yêu cầu**.

---

### Task 2: Shared prefix trên root (chưa cắt team)

**Files:**
- Modify: `src/domain/agents/graph.py` — `StateGraph(AssistantState)` với nodes: `guardrail_input`, `recall`, `rewrite`, `classify`, rồi **một** node `legacy_pipeline` tạm gọi tiếp logic flat còn lại **hoặc** edge vào compiled vms subgraph nếu đã tách được
- Prefer (ponytail): root wire prefix bằng import node từ `vms.nodes.*`, sau `classify` gọi node `delegate_rest` wrap `vms` remainder — **nếu quá rủi ro**, giữ Task 2 chỉ **move import path** prefix vào `domain.agents.nodes_prefix` và root graph vẫn compile full flat bằng copy wiring từ `vms.graph._build_graph` sang `domain.agents.graph.build_graph`, `vms.graph` re-export.

**Recommended path (smallest complete):** Copy `_build_graph` wiring từ `vms/graph.py` → `domain/agents/graph.py` (full flat vẫn chạy); `vms/graph.py` thành `from src.domain.agents.graph import *` shim ngược. Prefix nodes vẫn file `vms/nodes/*` (chưa move file).

**Interfaces:**
- Consumes: `guardrail_input_node`, `recall_node`, `rewrite_node`, `classify_node`, … từ `vms.nodes`
- Produces: `src.domain.agents.graph.build_graph` == canonical compile; tests cũ patch `vms.graph` vẫn pass nếu shim re-export `_build_graph = build_graph`

- [ ] **Step 1: Failing test — canonical import**

```python
def test_root_graph_is_canonical():
    import src.domain.agents.graph as root
    import src.domain.agents.vms.graph as vms
    assert root.build_graph is not None
    # sau shim ngược:
    g1 = root.build_graph()
    assert "guardrail_input" in g1.get_graph().nodes
```

- [ ] **Step 2: Run — FAIL hoặc assert sai nếu chưa move**

- [ ] **Step 3: Move `_build_graph` (+ helpers run/stream cần thiết) sang `domain/agents/graph.py`; `vms/graph.py` re-export**

Giữ tên node LangGraph. Không đổi edge.

- [ ] **Step 4:**

```bash
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py::test_graph_nodes_and_structure tests/test_v16_hierarchy_skeleton.py -q
```

Expected: PASS

- [ ] **Step 5: change-log + checkbox**

---

### Task 3: `analytics/` subgraph

**Files:**
- Create: `src/domain/agents/analytics/__init__.py`
- Create: `src/domain/agents/analytics/state.py`
- Create: `src/domain/agents/analytics/graph.py`
- Create: `src/domain/agents/analytics/nodes.py`
- Move (optional same task): `sql_agent/` → `analytics/sql_agent/` **hoặc** giữ path cũ + import từ analytics (ponytail: **giữ `sql_agent/` path**, analytics chỉ wire nodes — ít churn test)

**Interfaces:**
- Consumes: `retrieve_schema_node`, `generate_sql_node`, `validate_sql_node`, `repair_sql_node`, `execute_sql_node`, `render_chart_node` (+ batch helpers nếu multi nội bộ tạm)
- Produces:
  - `AnalyticsTeamState` (TypedDict) gồm field SQL/chart + `question`, `intent`, `user_id`, `session_id`
  - `def build_analytics_graph()` → `CompiledStateGraph` (subgraph)
  - Edges trong team: schema → generate → validate ⇄ repair → execute → render/respond_team_end
  - **Không** `run_agent` trong package

- [ ] **Step 1: Failing test**

```python
# tests/test_v16_analytics_subgraph.py
from src.domain.agents.analytics.graph import build_analytics_graph

def test_analytics_graph_has_sql_nodes():
    g = build_analytics_graph()
    nodes = set(g.get_graph().nodes)
    for n in ("retrieve_schema", "generate_sql", "validate_sql", "repair_sql", "execute_sql"):
        assert n in nodes
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `build_analytics_graph`** — cắt nhánh SQL+chart(+repair) từ root flat vào subgraph. Root tạm thời: `add_node("analytics_team", build_analytics_graph())` nhưng **chưa** bắt buộc multi supervisor (có thể vẫn flat route vào subgraph như một node).

Strangler trong task này: root `route` sau classify/orchestrator trỏ `analytics_team` thay vì từng SQL node lẻ.

- [ ] **Step 4:**

```bash
PYTHONPATH=. pytest tests/test_v16_analytics_subgraph.py tests/test_product_sql_agent.py -q --tb=no
```

Expected: analytics test PASS; sql_agent regressions: sửa import nếu break, không đổi logic.

- [ ] **Step 5: change-log**

---

### Task 4: `knowledge/` subgraph

**Files:**
- Create: `src/domain/agents/knowledge/__init__.py`
- Create: `src/domain/agents/knowledge/state.py`
- Create: `src/domain/agents/knowledge/graph.py`
- Create: `src/domain/agents/knowledge/nodes.py`
- Keep: `docs_agent/` path (ponytail) hoặc move under `knowledge/docs_agent/`

**Interfaces:**
- Consumes: `retrieve_docs_node`, `answer_from_docs_node`
- Produces: `KnowledgeTeamState`, `build_knowledge_graph()` với nodes `retrieve_docs` → `answer_from_docs`

- [ ] **Step 1: Failing test**

```python
from src.domain.agents.knowledge.graph import build_knowledge_graph

def test_knowledge_graph_nodes():
    nodes = set(build_knowledge_graph().get_graph().nodes)
    assert "retrieve_docs" in nodes
    assert "answer_from_docs" in nodes
```

- [ ] **Step 2–4: implement + pytest** `tests/test_v16_knowledge_subgraph.py` + subset `tests/test_product_knowledge_rag.py`

- [ ] **Step 5: change-log**

---

### Task 5: `top_supervisor` loop + root `synth`

**Files:**
- Modify: `src/domain/agents/nodes.py` — thật: plan steps / `next_team` / collect
- Modify: `src/domain/agents/graph.py` — wiring:

```text
START → guardrail → recall → rewrite → classify
  → top_supervisor ⇄ analytics_team | knowledge_team | synth
  → synth → guardrail_output → END
```

- Port logic từ `multi_agent/core.py` + `synth.py` (`orchestrator_collect` → supervisor/synth)
- Remove flat `orchestrator` / `orchestrator_collect` nodes khỏi root khi tương đương

**Interfaces:**
- Consumes: `plan_orchestration`, step_results pattern từ `multi_agent`
- Produces:
  - `top_supervisor_node(state) -> dict` sets `next_team` in `{"analytics_team","knowledge_team","synth"}`
  - `route_from_top(state) -> str`
  - `synth_node(state) -> dict` sets `final_answer` / answer fields tương đương `respond` cũ khi multi xong; single-team có thể synth mỏng forward answer từ team

- [ ] **Step 1: Failing tests**

```python
def test_route_greeting_to_synth():
    from src.domain.agents.nodes import route_from_top
    assert route_from_top({"intent": "chat", "next_team": "synth"}) == "synth"

def test_route_multi_continues_to_team():
    from src.domain.agents.nodes import route_from_top
    assert route_from_top({"next_team": "analytics_team"}) == "analytics_team"
```

Plus 1 integration: multi plan 2 SQL steps vẫn ra answer (reuse fixture từ `test_product_graph_orchestrator`).

- [ ] **Step 2–4: implement routes; run**

```bash
PYTHONPATH=. pytest tests/test_product_graph_orchestrator.py tests/test_v16_hierarchy_skeleton.py -q
```

- [ ] **Step 5: change-log** — xác nhận chỉ 2 loops (multi root + SQL repair in analytics)

---

### Task 6: `AgentTurnService` + SSE mới + frontend

**Files:**
- Replace/expand: `src/application/agent_turn.py`
- Modify: `src/api/routers/routes_agent.py`
- Modify: `src/main.py` — thin `run_agent` / `run_agent_stream` → service
- Modify: frontend SSE parser (đường dẫn UI trong monorepo/canvas nếu có consumer `node_id`/`__answer__` — grep ` __answer__` / `node_id` trước khi sửa)
- Create: `tests/test_v16_agent_turn_sse.py`

**Interfaces:**

```python
class TurnInput(BaseModel):
    question: str
    user_id: str
    session_id: str
    request_id: str = ""
    stream_tokens: bool = False

class TurnOutput(BaseModel):
    question: str
    answer: str
    detail: dict = {}
    # map từ final_answer / query như ChatResponse cần

class AgentTurnService:
    def request_deps(self) -> dict: ...
    def process(self, inp: TurnInput) -> TurnOutput: ...
    async def stream_sse(self, inp: TurnInput) -> AsyncIterator[str]: ...
```

`start_graph` yields:
- `("token", chunk)`
- `("node", {node, status, ...})`
- `("result", state_or_payload)`

SSE lines:

```text
data: {"token": "..."}
data: {"node": "generate_sql", "status": "done", ...}
data: {"complete": true, "question": "...", "answer": "...", "detail": {...}, "chart": {...}}
data: [DONE]
```

Error: `data: {"error": "..."}\n\n`

- [ ] **Step 1: Failing contract test**

```python
import json
from src.application.agent_turn import AgentTurnService, TurnInput

def test_stream_sse_complete_event_shape(monkeypatch):
    async def fake_start_graph(*a, **k):
        yield "result", {"final_answer": type("F", (), {"question": "q", "answer": "a", "detail": ""})()}
    monkeypatch.setattr("src.application.agent_turn.start_graph", fake_start_graph)
    # collect async stream_sse → assert one payload has complete True and answer
```

(Điều chỉnh mock đúng shape `final_answer` khi implement.)

- [ ] **Step 2: Implement service + `start_graph` thật map từ graph events**

- [ ] **Step 3: Router dùng service; bỏ rewrite/classify ở router**

- [ ] **Step 4: FE grep + update parse `complete` / `token` / `node`**

- [ ] **Step 5:**

```bash
PYTHONPATH=. pytest tests/test_v16_agent_turn_sse.py tests/test_product_memory_cache.py -q --tb=line
```

Sửa test cũ đang expect `__answer__` / `node_id`.

- [ ] **Step 6: change-log**

---

### Task 7: Cleanup dead code + AC

**Files:**
- Delete: cây trùng / shim không còn import (`vms/` flat dư, `agents/nodes|sql|routing|orchestrator|core` nếu còn)
- Modify: mọi test import → `src.domain.agents.graph` / teams
- Modify: `specs/README.md`, `specs/v16-hierarchical-agents-design.md` acceptance checkboxes, `product-spec.md` (đoạn flow graph + SSE nếu còn mô tả flat/`__answer__`)
- Modify: `specs/change-log.md`

**Interfaces:**
- Produces: không còn `vms.graph` như canonical (nếu giữ file: chỉ deprecated re-export 1 release)

- [ ] **Step 1: Inventory imports**

```bash
cd agent-harness/dong && rg "domain\\.agents\\.vms" --glob "*.py" -n
```

- [ ] **Step 2: Xóa file chết; sửa import**

- [ ] **Step 3: Full relevant suite**

```bash
PYTHONPATH=. pytest tests/test_v16_*.py tests/test_product_graph_orchestrator.py tests/test_product_sql_agent.py tests/test_product_knowledge_rag.py tests/test_product_memory_cache.py -q
```

Expected: PASS (hoặc liệt kê skip có lý do)

- [ ] **Step 4: Tick acceptance trong design:**
  - Root graph thật
  - analytics + knowledge subgraph
  - multi qua supervisor + synth; repair trong analytics
  - AgentTurnService là đường API
  - SSE mới + FE
  - dead code sạch

- [ ] **Step 5: change-log “v16 done”**

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Layout root/analytics/knowledge/application | 1,3,4,6 |
| Shared prefix trước supervisor | 2,5 |
| Team topology analytics \| knowledge | 3,4 |
| Multi A: supervisor loop + synth | 5 |
| SQL repair trong analytics | 3 |
| No new loop / no ReAct | Constraints + 5 |
| AgentTurnService như ChatService | 6 |
| SSE B + FE | 6 |
| Xóa shim/cây trùng | 7 |
| Phased / one task | Global + header |

**Placeholder scan:** không TBD.  
**Type names:** `AssistantState`, `AnalyticsTeamState`, `KnowledgeTeamState`, `TurnInput`, `TurnOutput`, `AgentTurnService`, `build_graph`, `start_graph`, `build_analytics_graph`, `build_knowledge_graph` — dùng nhất quán across tasks.

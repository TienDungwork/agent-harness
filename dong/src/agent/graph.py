"""Graph Agent — ReAct function-calling trên plate_event/zone_event (Postgres).

    START → seed → agent ⇄ tools → pack → END

1 LLM call (ReAct, thường 1-2 vòng tool) để CHỌN tool + điền tham số — không
tự sinh SQL cho câu hỏi khớp tool (xem src/agent/tools.py).

pack() dựng câu trả lời TEMPLATE (liệt kê số liệu thô) trước, rồi gọi
src/agent/answer.py (LLM call thứ 2, tuỳ chọn qua ANSWER_USE_LLM) để diễn
giải thành câu tiếng Việt tự nhiên — template luôn là fallback khi tắt LLM,
offline, hoặc lời gọi lỗi.

Observability: `run_agent(..., parent_span=)` nhận span cha từ
`trace_answer` (main); agent/tools/pack tạo nested `chon_tool` /
`chay_tool` / `dien_giai`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Any, TypedDict
import contextvars
import queue
import threading

from langgraph.graph.message import add_messages
from pydantic import BaseModel

from src.agent.answer import build_answer
from src.agent.react import all_tool_json, build_react_subgraph, fresh_user, parse_tool_output
from src.agent.tools import TOOLS, QueryResult
from src.monitoring.tracing import trace_step

from src.prompts import registry

__all__ = ["run_agent"]


class Agent_Input(BaseModel):
    question: str


class Agent_Output(BaseModel):
    question: str
    answer: str
    query: QueryResult | None = None
    detail: str = ""


import operator

class AgentState(TypedDict, total=False):
    question: str
    intent: str
    events: Annotated[list[dict], operator.add]
    result: Agent_Output
    messages: Annotated[list, add_messages]
    _trace_span: Any


_TOOL_NAMES = {t.name for t in TOOLS}

# LLM không biết ngày giờ thật (chỉ có kiến thức huấn luyện tới 1 mốc quá
# khứ) — PHẢI tiêm ngày giờ hiện tại vào system prompt, nếu không model sẽ tự
# bịa ngày (đã quan sát thực tế ở atin/: model trả lời bằng ngày trong dữ
# liệu huấn luyện, ra ngoài khoảng dữ liệu thật -> luôn 0 dòng cho câu hỏi
# "hôm nay"). system_prompt PHẢI là callable (đánh giá lại mỗi lượt gọi),
# không phải string cố định build 1 lần lúc compile graph.
# System prompt template được quản lý động qua PromptRegistry (prompts/agent_system).


def _system_prompt() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return registry().render("agent_system", version="production", now=now)


def _seed(state: AgentState) -> dict:
    question = str(state.get("question") or "").strip()
    return fresh_user(f"Câu hỏi: {question}")


def _offline(state: AgentState) -> tuple[str, dict]:
    # Không API key / pytest: đi thẳng qua list_khu_vuc — không gọi OpenAI.
    return "list_khu_vuc", {}


def _template_answer(queries: list[QueryResult]) -> str:
    """Gộp câu trả lời từ 1+ QueryResult — agent có thể gọi NHIỀU tool song
    song trong 1 lượt (vd. count_vehicle_flow(MOTORCYCLE) + (CAR) cho câu hỏi
    hỏi nhiều loại xe cùng lúc); bỏ sót tool nào là mất dữ liệu thật trong
    câu trả lời, đã phát hiện qua test 5 câu hỏi mẫu — xem change-log."""
    errors = [q.error for q in queries if q.error]
    if errors and len(errors) == len(queries):
        return " ".join(errors)

    all_rows: list[tuple[list[str], list]] = []
    for q in queries:
        if q.error:
            continue
        for row in q.rows:
            all_rows.append((q.columns, row))

    if not all_rows:
        return "Không có dữ liệu khớp câu hỏi trong khoảng thời gian/điều kiện đã cho."
    if len(all_rows) == 1 and len(all_rows[0][0]) == 1:
        return f"Kết quả: {all_rows[0][1][0]}"
    lines = [", ".join(f"{c}={v}" for c, v in zip(cols, row)) for cols, row in all_rows[:20]]
    return f"Kết quả ({len(all_rows)} dòng):\n" + "\n".join(lines)


def _pack(state: AgentState) -> dict:
    question = str(state.get("question") or "")
    raw_list = all_tool_json(state, _TOOL_NAMES)
    queries = [q for raw in raw_list if (q := parse_tool_output(raw, QueryResult)) is not None]
    step_input = {
        "tools": [q.tool for q in queries],
        "queries": [
            {"tool": q.tool, "row_count": q.row_count, "columns": q.columns}
            for q in queries
        ],
    }
    with trace_step(state.get("_trace_span"), "dien_giai", input=step_input) as t:
        if not queries:
            result = Agent_Output(
                question=question,
                answer="Chưa truy vấn được dữ liệu.",
                detail="không có kết quả tool",
            )
            t["output"] = {"answer": result.answer, "tools": []}
            return {"result": result}

        template = _template_answer(queries)
        answer = build_answer(question, queries, template)
        tools_used = ",".join(dict.fromkeys(q.tool for q in queries))
        result = Agent_Output(
            question=question,
            answer=answer,
            query=queries[-1],
            detail=f"tool: {tools_used}",
        )
        # Chỉ gắn câu trả lời ngắn + tên tool — không dump rows/secrets.
        t["output"] = {"answer": answer[:500], "tools": tools_used}
        return {"result": result}


from src.agent.intent import classify_intent
from src.agent.docs import handle_docs_intent

def classify_node(state: AgentState) -> dict:
    q = state.get("question", "")
    intent = classify_intent(q)
    return {"intent": intent, "events": [{"node_id": "classify_intent", "input": q, "output": intent}]}

def docs_node(state: AgentState) -> dict:
    q = state.get("question", "")
    ans = handle_docs_intent(q)
    result = Agent_Output(question=q, answer=ans, detail="docs")
    return {"result": result, "events": [{"node_id": "docs_node", "input": q, "output": ans[:200]}]}

def out_of_scope_node(state: AgentState) -> dict:
    from src.guardrails import OUT_OF_SCOPE_REPLY
    q = state.get("question", "")
    result = Agent_Output(question=q, answer=OUT_OF_SCOPE_REPLY, detail="out_of_scope")
    return {"result": result, "events": [{"node_id": "out_of_scope_node", "input": q, "output": OUT_OF_SCOPE_REPLY[:200]}]}

def call_react_node(state: AgentState) -> dict:
    res = build_react_subgraph(
        AgentState,
        tools=TOOLS,
        system_prompt=_system_prompt,
        offline_call=_offline,
        seed_fn=_seed,
        pack_fn=_pack,
    ).compile().invoke(state)
    ans = ""
    if res.get("result"):
        ans = getattr(res.get("result"), "answer", "")
    return {"result": res.get("result"), "events": [{"node_id": "react_node", "input": state.get("question", ""), "output": ans[:200]}]}

def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    elif intent == "out_of_scope":
        return "out"
    return "react"


_stream_queue = contextvars.ContextVar("_stream_queue", default=None)

def _wrap_node(node_id: str, func):
    def wrapper(state: AgentState):
        q = _stream_queue.get()
        if q is not None:
            q.put({"node_id": node_id, "status": "running"})
        
        try:
            res = func(state)
        except Exception as e:
            if q is not None:
                q.put({
                    "node_id": node_id,
                    "status": "done",
                    "output": f"Lỗi hệ thống: {str(e)}"
                })
            raise
        
        if q is not None:
            if isinstance(res, dict) and "events" in res and res["events"]:
                for ev in res["events"]:
                    q.put({
                        "node_id": ev.get("node_id", node_id),
                        "status": "done",
                        "input": ev.get("input", ""),
                        "output": ev.get("output", "")
                    })
            else:
                q.put({
                    "node_id": node_id,
                    "status": "done",
                    "input": "",
                    "output": ""
                })
        return res
    return wrapper

@lru_cache(maxsize=1)
def _build_graph():
    from langgraph.graph import StateGraph, START, END
    graph = StateGraph(AgentState)
    graph.add_node("classify", _wrap_node("classify_intent", classify_node))
    graph.add_node("docs", _wrap_node("docs_node", docs_node))
    graph.add_node("out", _wrap_node("out_of_scope_node", out_of_scope_node))
    graph.add_node("react", _wrap_node("react_node", call_react_node))
    
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_intent, {"docs": "docs", "out": "out", "react": "react"})
    graph.add_edge("docs", END)
    graph.add_edge("out", END)
    graph.add_edge("react", END)
    return graph.compile()

def run_agent(inp: Agent_Input, parent_span: Any = None) -> Agent_Output:
    """`parent_span`: span cha từ `trace_answer` (main). None = không trace con."""
    question = (inp.question or "").strip()
    return _build_graph().invoke({"question": question, "_trace_span": parent_span, "events": []})["result"]


def save_graph_visualization(path: str = "graph.png") -> str:
    """Xuất sơ đồ graph ra file PNG, Mermaid (.mmd) và HTML trực quan (.html) —
    hữu ích để debug/trình bày cấu trúc ReAct (seed → agent ⇄ tools → pack).
    """
    graph = _build_graph().get_graph()
    mermaid_code = graph.draw_mermaid()

    # 1. Ghi tệp Mermaid text thuần (.mmd)
    mmd_path = path.rsplit(".", 1)[0] + ".mmd"
    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid_code)

    # 2. Ghi tệp HTML trực quan (.html)
    html_path = path.rsplit(".", 1)[0] + "_diagram.html"
    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>Sơ đồ Đồ thị ReAct Agent — agent_ATIN</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #fbfbf9; padding: 1rem; }}
    .card {{ background: #ffffff; padding: 2rem; border-radius: 12px; border: 1px solid #e5e4dc; box-shadow: 0 4px 12px rgba(0,0,0,0.06); max-width: 900px; width: 100%; text-align: center; }}
    h2 {{ color: #1c1b18; margin-bottom: 0.5rem; }}
    p {{ color: #636159; font-size: 0.95rem; margin-bottom: 1.5rem; }}
    code {{ background: #f0eee6; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; }}
    .mermaid {{ margin: 1rem 0; display: flex; justify-content: center; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Sơ đồ Đồ thị ReAct Agent (LangGraph)</h2>
    <p>Kiến trúc ReAct Agent: <code>START → seed → agent ⇄ tools → pack → END</code></p>
    <div class="mermaid">
{mermaid_code}
    </div>
  </div>
  <script>mermaid.initialize({{startOnLoad:true, theme: 'neutral'}});</script>
</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 3. Thử xuất tệp ảnh PNG (cần mạng gọi mermaid.ink)
    try:
        png_bytes = graph.draw_mermaid_png()
        with open(path, "wb") as f:
            f.write(png_bytes)
        return path
    except Exception:
        # Fallback về đường dẫn HTML/Mermaid
        return html_path


if __name__ == "__main__":
    # python -m src.agent.graph
    output = save_graph_visualization("graph.png")
    print(f"Graph visualization exported to: {output}")


def run_agent_stream(inp: Agent_Input, parent_span: Any = None):
    """Yield dict events for SSE stream."""
    question = (inp.question or "").strip()
    
    q = queue.Queue()
    _stream_queue.set(q)
    ctx = contextvars.copy_context()
    
    def target():
        try:
            res = ctx.run(_build_graph().invoke, {"question": question, "_trace_span": parent_span, "events": []})
            if res and "result" in res:
                q.put({"__final_result__": res["result"]})
        except Exception as e:
            from src.main import _format_error_message
            msg = _format_error_message(e)
            q.put({"node_id": "error", "status": "done", "output": f"Lỗi hệ thống: {str(e)}"})
            q.put({"node_id": "__answer__", "status": "error", "output": msg, "detail": {"status": "error"}})
        finally:
            q.put(None)
            
    t = threading.Thread(target=target)
    t.start()
    
    while True:
        ev = q.get()
        if ev is None:
            break
        yield ev
    
    t.join()
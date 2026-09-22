"""Graph Agent v5 — LangGraph pipeline thay thế ReAct.

Pipeline chính:
  START → rewrite → classify → [route]
    - query_data: retrieve_schema → plan_query → validate → execute → [render_chart] → respond → END
    - docs: retrieve_docs → answer_from_docs → END
    - out: out_of_scope_node → END
"""

from __future__ import annotations

import contextvars
import queue
import re
import threading
from typing import Annotated, Any, TypedDict
import operator

from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from src.agent.intent import classify_intent
from src.agent.rewrite import rewrite_question
from src.db.catalog import build_schema_excerpt
from src.agent.query_plan import plan_query, repair_plan_query
from src.db.query_builder import build_sql
from src.db.validator import validate_sql
from src.db.executor import execute_sql
from src.chart.render import should_render_chart, plan_chart, render_chart
from src.llm.schemas import ChartSpec, QueryPlan, RewrittenQuestion, StatAnswer
from src.guardrails import OUT_OF_SCOPE_REPLY
from src.agent.tools import QueryResult
from src.monitoring.tracing import trace_step

class Agent_Input(BaseModel):
    question: str
    rewritten: Any | None = None

class Agent_Output(BaseModel):
    question: str
    answer: str
    query: QueryResult | None = None
    detail: str = ""

class AgentState(TypedDict, total=False):
    question: str
    rewritten: RewrittenQuestion
    intent: str
    
    # Query Data branch
    schema_excerpt: str
    plan: QueryPlan
    sql: str
    params: list
    rows: list
    columns: list
    error: str
    chart_png_base64: str
    chart_spec: ChartSpec
    
    events: Annotated[list[dict], operator.add]
    result: Agent_Output
    _trace_span: Any

_stream_queue = contextvars.ContextVar("_stream_queue", default=None)

def _wrap_node(node_id: str, func):
    def wrapper(state: AgentState):
        q = _stream_queue.get()
        parent = state.get("_trace_span")
        if q is not None:
            q.put({"node_id": node_id, "status": "running"})

        with trace_step(parent, node_id) as step:
            try:
                res = func(state)
            except Exception as e:
                step["input"] = ""
                step["output"] = f"Lỗi hệ thống: {str(e)}"
                if q is not None:
                    q.put({
                        "node_id": node_id,
                        "status": "done",
                        "output": step["output"],
                    })
                raise

            if isinstance(res, dict) and "events" in res and res["events"]:
                ev = res["events"][-1]
                step["input"] = ev.get("input", "")
                step["output"] = ev.get("output", "")
                if ev.get("meta"):
                    step["metadata"] = ev["meta"]
                if q is not None:
                    for item in res["events"]:
                        q.put({
                            "node_id": item.get("node_id", node_id),
                            "status": "done",
                            "input": item.get("input", ""),
                            "output": item.get("output", ""),
                            "chart_png_base64": item.get("chart_png_base64"),
                            "chart_meta": item.get("chart_meta"),
                        })
            else:
                step["input"] = ""
                step["output"] = ""
                if q is not None:
                    q.put({
                        "node_id": node_id,
                        "status": "done",
                        "input": "",
                        "output": "",
                    })
            return res
    return wrapper

def rewrite_node(state: AgentState) -> dict:
    from src.llm.client import use_offline_tools

    q = state.get("question", "")
    rewritten = state.get("rewritten")
    llm_used = False
    if not rewritten:
        llm_used = not use_offline_tools()
        rewritten = rewrite_question(q)
    return {
        "rewritten": rewritten,
        "question": rewritten.text,
        "events": [{
            "node_id": "rewrite",
            "input": q,
            "output": rewritten.model_dump_json(),
            "meta": {"llm_used": llm_used},
        }],
    }

def classify_node(state: AgentState) -> dict:
    from src.llm.client import use_offline_tools

    rewritten = state["rewritten"]
    llm_used = not use_offline_tools()
    res = classify_intent(rewritten)
    intent = res.intent
    return {
        "intent": intent,
        "events": [{
            "node_id": "classify",
            "input": rewritten.text,
            "output": res.model_dump_json(),
            "meta": {"llm_used": llm_used, "intent": intent},
        }],
    }

def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    elif intent == "out_of_scope":
        return "out"
    return "query_data"

def retrieve_docs_node(state: AgentState) -> dict:
    from src.knowledge import retrieve_docs
    q = state.get("question", "")
    cards = retrieve_docs(q)
    return {
        "events": [{"node_id": "retrieve_docs", "input": q, "output": f"Tìm thấy {len(cards)} cards"}],
        "rows": cards  # temporary save cards in rows
    }

def answer_from_docs_node(state: AgentState) -> dict:
    from src.knowledge import answer_from_docs
    q = state.get("question", "")
    cards = state.get("rows", [])
    docs_ans = answer_from_docs(q, cards)
    result = Agent_Output(question=q, answer=docs_ans.answer_vi, detail="docs")
    return {
        "result": result,
        "events": [{"node_id": "answer_from_docs", "input": f"{len(cards)} cards", "output": docs_ans.answer_vi[:200]}]
    }

def out_of_scope_node(state: AgentState) -> dict:
    q = state.get("question", "")
    result = Agent_Output(question=q, answer=OUT_OF_SCOPE_REPLY, detail="out_of_scope")
    return {
        "result": result,
        "events": [{"node_id": "out_of_scope", "input": q, "output": OUT_OF_SCOPE_REPLY[:200]}]
    }

def retrieve_schema_node(state: AgentState) -> dict:
    excerpt = build_schema_excerpt()
    return {
        "schema_excerpt": excerpt,
        "events": [{"node_id": "retrieve_schema", "input": "", "output": f"Schema length: {len(excerpt)}"}]
    }

def plan_query_node(state: AgentState) -> dict:
    rewritten = state["rewritten"]
    excerpt = state["schema_excerpt"]
    plan = plan_query(rewritten, excerpt)
    return {
        "plan": plan,
        "events": [{"node_id": "plan_query", "input": rewritten.text, "output": plan.model_dump_json()}]
    }

def validate_node(state: AgentState) -> dict:
    plan = state["plan"]
    rewritten = state["rewritten"]
    excerpt = state["schema_excerpt"]
    
    from src.config import settings
    limit_repairs = settings.sql_repair_max
    
    sql, params, error = "", [], None
    current_plan = plan
    
    for attempt in range(limit_repairs + 1):
        try:
            sql, params = build_sql(current_plan)
        except Exception as e:
            err = f"Lỗi tạo SQL: {e}"
            if attempt < limit_repairs:
                current_plan = repair_plan_query(rewritten, excerpt, current_plan, err)
                continue
            error = err
            break
            
        val = validate_sql(sql)
        if not val.ok:
            err = f"Lỗi validate SQL: {val.reason}"
            if attempt < limit_repairs:
                current_plan = repair_plan_query(rewritten, excerpt, current_plan, err)
                continue
            error = err
            break
            
        error = None
        break
        
    if error:
        raise ValueError(error)
        
    return {
        "sql": sql,
        "params": params,
        "plan": current_plan,
        "events": [{"node_id": "validate", "input": current_plan.model_dump_json(), "output": f"OK: {sql}"}]
    }

def execute_node(state: AgentState) -> dict:
    if state.get("error"):
        return {
            "rows": [],
            "columns": [],
            "events": [{"node_id": "execute", "input": "", "output": "Bỏ qua do lỗi validate"}]
        }
        
    sql = state["sql"]
    params = state["params"]
    
    try:
        rows = execute_sql(sql, params)
        columns = list(rows[0].keys()) if rows else []
        return {
            "rows": rows,
            "columns": columns,
            "events": [{"node_id": "execute", "input": sql, "output": f"Tra ve {len(rows)} dong"}]
        }
    except Exception as e:
        raise RuntimeError(f"Lỗi truy vấn cơ sở dữ liệu: {e}")

def should_render_chart_edge(state: AgentState) -> str:
    if state.get("error"):
        return "respond"
    q = state.get("question", "")
    # StatAnswer.chart_requested chưa có trước respond — dùng keyword trên câu (sau rewrite).
    if should_render_chart(q):
        return "render_chart"
    return "respond"

def render_chart_node(state: AgentState) -> dict:
    """Vẽ chart nếu được; lỗi render → bỏ chart, vẫn để respond trả text."""
    rows = state.get("rows", [])
    q = state.get("question", "")
    try:
        spec = plan_chart(rows, q)
        png_base64 = render_chart(rows, spec)
        meta = spec.model_dump() if spec else {}
        ok = bool(png_base64)
        return {
            "chart_png_base64": png_base64 or "",
            "chart_spec": spec,
            "events": [{
                "node_id": "render_chart",
                "input": f"{len(rows)} rows",
                "output": "Chart rendered" if ok else "Empty chart",
                "chart_png_base64": png_base64 or "",
                "chart_meta": meta,
            }],
        }
    except Exception as e:
        return {
            "chart_png_base64": "",
            "events": [{
                "node_id": "render_chart",
                "input": f"{len(rows)} rows",
                "output": f"Bỏ qua chart: {e}",
                "chart_png_base64": "",
            }],
        }

STAT_RESPOND_SYSTEM_PROMPT = (
    "Bạn là trợ lý dữ liệu. Trả lời bằng tiếng Việt ngắn gọn (1–2 câu). "
    "Không suy nghĩ, không dùng tag, không giải thích quy trình."
)


_THINKING_BLOCK = re.compile(r"\x3cthink\x3e.*?\x3c/think\x3e", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Bỏ block reasoning Qwen3."""
    if re.search(r"\x3cthink\x3e", text, re.IGNORECASE) and not re.search(
        r"\x3c/think\x3e", text, re.IGNORECASE
    ):
        return ""
    return _THINKING_BLOCK.sub("", text).strip()


def respond_node(state: AgentState) -> dict:
    q = state.get("question", "")
    error = state.get("error")
    rows = state.get("rows", [])
    columns = state.get("columns", [])
    
    from src.llm.client import invoke_text, use_offline_tools
    
    answer_source = "template"
    llm_used = False
    if error:
        ans = f"Lỗi khi truy vấn: {error}"
        answer_source = "error"
    elif not rows:
        ans = "Không có dữ liệu khớp câu hỏi trong khoảng thời gian/điều kiện đã cho."
        answer_source = "empty"
    else:
        lines = [", ".join(f"{c}={r[c]}" for c in columns) for r in rows[:20]]
        template_ans = f"Kết quả ({len(rows)} dòng):\n" + "\n".join(lines)
        ans = template_ans

        if not use_offline_tools():
            llm_used = True
            try:
                raw = invoke_text(
                    STAT_RESPOND_SYSTEM_PROMPT,
                    f"Câu hỏi: {q}\nDữ liệu:\n{template_ans}",
                )
                polished = _strip_thinking(raw)
                if polished:
                    ans = polished
                    answer_source = "llm_text"
            except Exception as exc:
                answer_source = f"template_fallback:{type(exc).__name__}"

    stat = StatAnswer(
        answer_vi=ans,
        highlights=[],
        chart_requested=should_render_chart(q) or bool(state.get("chart_png_base64")),
    )
    ans = stat.answer_vi

    query_res = QueryResult(
        tool="sql_builder",
        columns=columns,
        rows=[[r[c] for c in columns] for r in rows] if rows else [],
        row_count=len(rows) if rows else 0,
        error=error or "",
        reply_vi=ans
    )
    
    result = Agent_Output(question=q, answer=ans, query=query_res, detail="query_data")
    return {
        "result": result,
        "events": [{
            "node_id": "respond",
            "input": f"{len(rows)} rows | cols={columns}",
            "output": stat.model_dump_json(),
            "meta": {
                "llm_used": llm_used,
                "answer_source": answer_source,
                "stat_answer": stat.model_dump(),
            },
        }],
    }

def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("rewrite", _wrap_node("rewrite", rewrite_node))
    graph.add_node("classify", _wrap_node("classify", classify_node))
    graph.add_node("retrieve_schema", _wrap_node("retrieve_schema", retrieve_schema_node))
    graph.add_node("plan_query", _wrap_node("plan_query", plan_query_node))
    graph.add_node("validate", _wrap_node("validate", validate_node))
    graph.add_node("execute", _wrap_node("execute", execute_node))
    graph.add_node("render_chart", _wrap_node("render_chart", render_chart_node))
    graph.add_node("respond", _wrap_node("respond", respond_node))
    
    graph.add_node("retrieve_docs", _wrap_node("retrieve_docs", retrieve_docs_node))
    graph.add_node("answer_from_docs", _wrap_node("answer_from_docs", answer_from_docs_node))
    
    graph.add_node("out_of_scope", _wrap_node("out_of_scope", out_of_scope_node))
    
    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "classify")
    
    graph.add_conditional_edges("classify", route_intent, {
        "query_data": "retrieve_schema",
        "docs": "retrieve_docs",
        "out": "out_of_scope"
    })
    
    # Query Data branch
    graph.add_edge("retrieve_schema", "plan_query")
    graph.add_edge("plan_query", "validate")
    graph.add_edge("validate", "execute")
    graph.add_conditional_edges("execute", should_render_chart_edge, {
        "render_chart": "render_chart",
        "respond": "respond"
    })
    graph.add_edge("render_chart", "respond")
    graph.add_edge("respond", END)
    
    # Docs branch
    graph.add_edge("retrieve_docs", "answer_from_docs")
    graph.add_edge("answer_from_docs", END)
    
    # Out branch
    graph.add_edge("out_of_scope", END)
    
    return graph.compile()

def run_agent(inp: Agent_Input, parent_span: Any = None) -> Agent_Output:
    question = (inp.question or "").strip()
    return _build_graph().invoke({"question": question, "rewritten": inp.rewritten, "_trace_span": parent_span, "events": []})["result"]

def run_agent_stream(inp: Agent_Input, parent_span: Any = None):
    question = (inp.question or "").strip()
    
    q = queue.Queue()
    _stream_queue.set(q)
    ctx = contextvars.copy_context()
    
    def target():
        try:
            res = ctx.run(_build_graph().invoke, {"question": question, "rewritten": inp.rewritten, "_trace_span": parent_span, "events": []})
            if res and "result" in res:
                q.put({"__final_result__": res["result"]})
        except Exception as e:
            from src.main import _format_error_message
            msg = _format_error_message(e)
            q.put({"node_id": "error", "status": "done", "output": msg})
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

def save_graph_visualization(path: str = "graph.png") -> str:
    """Xuất sơ đồ LangGraph: PNG + Mermaid source + HTML xem trên browser."""
    graph = _build_graph().get_graph()
    mermaid_code = graph.draw_mermaid()
    base = path.rsplit(".", 1)[0]
    mmd_path = f"{base}.mmd"
    png_path = path if path.endswith(".png") else f"{base}.png"
    html_path = f"{base}_diagram.html"

    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid_code)
    with open(png_path, "wb") as f:
        f.write(graph.draw_mermaid_png())
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(
            "<!DOCTYPE html><html lang=\"vi\"><head><meta charset=\"UTF-8\">"
            "<title>Agent graph v5</title>"
            "<script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>"
            "</head><body><div class=\"mermaid\">\n"
            f"{mermaid_code}\n"
            "</div><script>mermaid.initialize({{startOnLoad:true}});</script></body></html>"
        )
    return png_path


if __name__ == "__main__":
    png = save_graph_visualization("graph.png")
    print(f"Exported: {png}, graph.mmd, graph_diagram.html")

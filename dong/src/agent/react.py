"""ReAct helper — seed → agent ⇄ tools → pack. Hạ tầng dùng chung cho graph
(src/agent/graph.py), không phải business logic riêng.

Offline (không API key / pytest): giả 1 tool_call (`offline_call`) thay vì
gọi OpenAI thật — test/CI không phụ thuộc network.

Observability (Phase 5): agent/tools đọc `state["_trace_span"]` (span cha từ
`trace_answer` ở main) và tạo nested `trace_step` — no-op khi span là None.
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.config import settings
from src.llm import invoke_with_tools, use_offline_tools
from src.monitoring.tracing import extract_token_usage, trace_step


def fresh_user(text: str) -> dict:
    from langchain_core.messages import RemoveMessage
    from langgraph.graph.message import REMOVE_ALL_MESSAGES

    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), {"role": "user", "content": text}]}


def should_continue(state: dict) -> str:
    last = (state.get("messages") or [None])[-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "pack"


def _is_tool_result(msg) -> bool:
    return bool(getattr(msg, "tool_call_id", None) or getattr(msg, "type", None) == "tool")


def _tool_call_summary(tool_calls: list) -> list[dict]:
    """Tóm tắt tool_calls cho Langfuse — tên + args, không dump message dài."""
    out: list[dict] = []
    for c in tool_calls or []:
        if isinstance(c, dict):
            out.append({"name": c.get("name"), "args": c.get("args")})
        else:
            out.append({"name": getattr(c, "name", None), "args": getattr(c, "args", None)})
    return out


def agent_node(state: dict, *, tools: list, system_prompt, offline_call) -> dict:
    from langchain_core.messages import AIMessage

    span = state.get("_trace_span")
    with trace_step(span, "chon_tool", input=state.get("question") or "") as t:
        last = (state.get("messages") or [None])[-1]
        if use_offline_tools():
            if _is_tool_result(last):
                t["output"] = {"offline": True, "phase": "after_tool"}
                return {"messages": [AIMessage(content="ok")]}
            name, args = offline_call(state)
            t["output"] = {"offline": True, "tool_calls": [{"name": name, "args": args}]}
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": name, "args": args, "id": "offline-1", "type": "tool_call"}],
                    )
                ]
            }

        # system_prompt có thể là string tĩnh hoặc callable (đánh giá lại mỗi lượt —
        # cần khi prompt tiêm giờ hiện tại, xem src/agent/graph.py).
        prompt_text = system_prompt() if callable(system_prompt) else system_prompt
        messages = [{"role": "system", "content": prompt_text}] + list(state.get("messages") or [])
        try:
            response = invoke_with_tools(messages, tools)
        except Exception as exc:
            t["output"] = {"error": str(exc)}
            return {"messages": [AIMessage(content=f"Lỗi LLM: {exc}. Thử lại hoặc hỏi lại câu khác.")]}

        usage = extract_token_usage(response)
        model_name = getattr(response, "response_metadata", {}).get("model_name") or (
            settings.model_name if settings.llm_backend == "self_hosted" else settings.llm_model
        )
        t["usage"] = usage
        t["model_name"] = model_name
        t["temperature"] = settings.llm_temperature
        t["output"] = {
            "tool_calls": _tool_call_summary(getattr(response, "tool_calls", None) or []),
            "tokens": usage,
        }
        return {"messages": [response]}


def last_tool_json(state: dict, names: set[str]) -> str:
    for m in reversed(list(state.get("messages") or [])):
        name = getattr(m, "name", None) or ""
        if name in names and getattr(m, "content", None):
            return str(m.content)
    return ""


def _is_tool_message(m) -> bool:
    return bool(getattr(m, "tool_call_id", None) or getattr(m, "type", None) == "tool")


def all_tool_json(state: dict, names: set[str]) -> list[str]:
    """Toàn bộ tool message của LƯỢT TOOL-CALL GẦN NHẤT (không phải cả hội
    thoại) — cần khi agent gọi NHIỀU tool song song trong 1 lượt (LangChain
    cho phép 1 AIMessage mang nhiều tool_calls cùng lúc). `last_tool_json`
    chỉ lấy tool message cuối cùng nên bỏ sót các tool khác gọi cùng lượt —
    dùng hàm này khi pack() cần gộp đủ dữ liệu, không chỉ 1 tool.

    Message cuối luôn là AIMessage (câu trả lời tổng hợp cuối, không phải
    tool call) — bỏ qua nó trước, rồi thu thập các ToolMessage liên tiếp
    ngay phía trước cho tới khi hết (gặp AIMessage/HumanMessage khác)."""
    messages = list(state.get("messages") or [])
    results: list[str] = []
    for m in reversed(messages[:-1]):  # bỏ AIMessage cuối cùng
        if not _is_tool_message(m):
            break  # hết lượt tool-call gần nhất
        name = getattr(m, "name", None) or ""
        if name in names and getattr(m, "content", None):
            results.append(str(m.content))
    results.reverse()
    return results


def parse_tool_output(raw: str, cls):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return cls.model_validate_json(text)
    except Exception:
        return None


def _tools_node(state: dict, *, tools: list) -> dict:
    """ToolNode có nested span `chay_tool` — chỉ ghi tên tool, không dump rows."""
    span = state.get("_trace_span")
    with trace_step(span, "chay_tool", input=state.get("question") or "") as t:
        result = ToolNode(tools).invoke(state)
        names = [
            getattr(m, "name", None)
            for m in (result.get("messages") or [])
            if getattr(m, "name", None)
        ]
        t["output"] = {"tools": names}
        return result


def build_react_subgraph(state_cls, *, tools: list, system_prompt, offline_call, seed_fn, pack_fn):
    graph = StateGraph(state_cls)
    graph.add_node("seed", seed_fn)
    graph.add_node("agent", partial(agent_node, tools=tools, system_prompt=system_prompt, offline_call=offline_call))
    graph.add_node("tools", partial(_tools_node, tools=tools))
    graph.add_node("pack", pack_fn)

    graph.add_edge(START, "seed")
    graph.add_edge("seed", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "pack": "pack"})
    graph.add_edge("tools", "agent")
    graph.add_edge("pack", END)
    return graph

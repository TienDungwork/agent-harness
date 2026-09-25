from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_PROMPT = Path(__file__).resolve().parents[4] / "prompts" / "web_agent.md"


def answer_from_web(state: AgentState) -> dict:
    if state.get("error"):
        return {
            "answer": (
                "Không tra cứu web được lúc này. "
                f"Chi tiết: {state.get('error')}. "
                "Kiểm tra SearXNG đang chạy (docker compose trong infra/searxng)."
            ),
            "sql": "",
            "query_result": {},
            "sql_validation": {"ok": True, "reason": "web-search-error"},
        }

    results = state.get("web_results") or []
    if not results:
        return {
            "answer": (
                "Đã tìm trên web nhưng chưa có kết quả phù hợp. "
                "Bạn thử hỏi cụ thể hơn hoặc dùng từ khóa tiếng Anh/Việt rõ ràng hơn."
            ),
            "web_sources": [],
            "sql": "",
            "query_result": {},
            "sql_validation": {"ok": True, "reason": "web-no-results"},
        }

    system = _PROMPT.read_text(encoding="utf-8")
    user = (
        f"Câu hỏi:\n{state.get('question')}\n\n"
        f"Kết quả tìm kiếm:\n{state.get('web_excerpt') or ''}\n"
    )
    resp = get_llm(max_tokens=420).invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    sources = [
        {"title": str(r.get("title") or r.get("url") or ""), "url": str(r.get("url") or "")}
        for r in results[:3]
        if r.get("url")
    ]
    return {
        "answer": str(resp.content).strip(),
        "web_sources": sources,
        "sql": "",
        "query_result": {},
        "sql_validation": {"ok": True, "reason": "answered-from-web"},
    }

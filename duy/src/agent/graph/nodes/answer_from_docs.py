from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_PROMPT = Path(__file__).resolve().parents[4] / "prompts" / "docs_agent.md"


def answer_from_docs(state: AgentState) -> dict:
    docs = state.get("relevant_docs") or []
    if not docs:
        return {
            "answer": (
                "Trong tài liệu hướng dẫn hiện có chưa khớp đủ với câu hỏi này. "
                "Bạn mô tả rõ hơn thao tác hoặc màn hình đang xem được không?"
            ),
            "sql": "",
            "query_result": {},
            "sql_validation": {"ok": True, "reason": "docs-no-card"},
        }

    system = _PROMPT.read_text(encoding="utf-8")
    user = (
        f"Câu hỏi:\n{state.get('question')}\n\n"
        f"Task cards:\n{state.get('docs_excerpt')}\n"
    )
    resp = get_llm(max_tokens=450).invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    primary = docs[0] if docs else {}
    return {
        "answer": str(resp.content).strip(),
        "doc_card_id": str(primary.get("id") or ""),
        "doc_card_title": str(primary.get("title") or ""),
        "sql": "",
        "query_result": {},
        "sql_validation": {"ok": True, "reason": "answered-from-docs"},
    }

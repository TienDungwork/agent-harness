from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_SYSTEM = """Bạn là DUY — trợ lý VMS local (số liệu Postgres chỉ-đọc + hướng dẫn dùng hệ thống).
Trả lời tiếng Việt, ngắn, tự nhiên.
- Không bịa số liệu từ DB.
- Không chạy hay giả vờ đã query.
- Nếu intent=chat: đáp xã giao; gợi ý hỏi số liệu hoặc cách thao tác (thêm camera, xem live…).
- Nếu intent=clarify: hỏi lại để phân biệt số liệu vs hướng dẫn.
- Nếu intent=out_of_scope: từ chối lịch sự.
"""


def respond_without_sql(state: AgentState) -> dict:
    intent = state.get("intent") or "chat"
    user = (
        f"intent={intent}\n"
        f"reason={state.get('intent_reason') or ''}\n"
        f"Câu người dùng: {state.get('question')}\n"
    )
    resp = get_llm(temperature=0.3, max_tokens=160).invoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=user)]
    )
    return {
        "answer": str(resp.content).strip(),
        "sql": "",
        "query_result": {},
        "sql_validation": {"ok": True, "reason": "skipped-sql"},
    }

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_PROMPT = Path(__file__).resolve().parents[4] / "prompts" / "sql_agent.md"
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def repair_sql(state: AgentState) -> dict:
    system = _PROMPT.read_text(encoding="utf-8")
    user = (
        f"Câu SQL trước bị từ chối hoặc chạy lỗi.\n"
        f"Lý do validation: {state.get('sql_validation', {}).get('reason')}\n"
        f"Lỗi execute: {state.get('error') or ''}\n"
        f"SQL cũ:\n{state.get('sql')}\n\n"
        f"Câu hỏi:\n{state.get('question')}\n\n"
        f"Schema excerpt:\n{state.get('schema_excerpt')}\n\n"
        "Hãy viết lại một câu SELECT hợp lệ. Chỉ dùng bảng và cột có trong schema excerpt; "
        "không gắn cột của bảng này vào bảng kia."
    )
    resp = get_llm(max_tokens=280).invoke([SystemMessage(content=system), HumanMessage(content=user)])
    m = _SQL_FENCE.search(str(resp.content) or "")
    sql = ((m.group(1) if m else str(resp.content)) or "").strip().rstrip(";")
    return {
        "sql": sql,
        "repair_count": int(state.get("repair_count") or 0) + 1,
    }

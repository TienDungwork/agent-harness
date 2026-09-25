from __future__ import annotations

import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm
from agent.services.chart_hint import build_chart_sql_hint

_PROMPT = Path(__file__).resolve().parents[4] / "prompts" / "sql_agent.md"
_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _extract_sql(text: str) -> str:
    m = _SQL_FENCE.search(text or "")
    body = (m.group(1) if m else text) or ""
    return body.strip().rstrip(";")


def generate_sql(state: AgentState) -> dict:
    system = _PROMPT.read_text(encoding="utf-8")
    datasets = state.get("relevant_datasets") or []
    primary = ""
    if datasets:
        ds0 = datasets[0]
        primary = (
            f"Bảng ưu tiên: {ds0.get('table')} (database {ds0.get('database')}). "
            "FROM đúng bảng này trừ khi câu hỏi rõ ràng cần bảng khác trong excerpt.\n\n"
        )
    chart_hint = build_chart_sql_hint(str(state.get("question") or ""))
    user = (
        f"{primary}{chart_hint}"
        f"Câu hỏi:\n{state.get('question')}\n\n"
        f"Schema excerpt:\n{state.get('schema_excerpt')}\n"
    )
    resp = get_llm(max_tokens=280).invoke([SystemMessage(content=system), HumanMessage(content=user)])
    sql = _extract_sql(str(resp.content))
    return {"sql": sql, "error": ""}

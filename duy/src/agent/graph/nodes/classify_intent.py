from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_PROMPT = Path(__file__).resolve().parents[4] / "prompts" / "intent.md"
_ALLOWED = frozenset(
    {
        "query_db",
        "how_to",
        "troubleshoot",
        "concept",
        "web_search",
        "chat",
        "clarify",
        "out_of_scope",
    }
)
_NEEDS_PIPELINE = frozenset({"query_db", "how_to", "troubleshoot", "concept", "web_search"})


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_intent_payload(text: str) -> tuple[str, str, str]:
    data = _extract_json_object(text)
    if data:
        intent = str(data.get("intent") or "").strip().lower()
        reason = str(data.get("reason") or "").strip()
        answer = str(data.get("answer") or "").strip()
        if intent in _ALLOWED:
            if intent in _NEEDS_PIPELINE:
                answer = ""
            return intent, reason, answer

    lowered = (text or "").strip().lower()
    for name in _ALLOWED:
        if re.search(rf"\b{name}\b", lowered):
            return name, "parsed-from-text", ""

    return (
        "clarify",
        "unparsed-intent",
        "Bạn muốn hỏi số liệu trong hệ thống hay hướng dẫn thao tác trên VMS?",
    )


def classify_intent(state: AgentState) -> dict:
    system = _PROMPT.read_text(encoding="utf-8")
    question = (state.get("question") or "").strip()
    resp = get_llm(max_tokens=140).invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=f"Câu người dùng:\n{question}"),
        ]
    )
    intent, reason, answer = parse_intent_payload(str(resp.content))
    out: dict = {
        "intent": intent,
        "intent_reason": reason,
        "error": "",
        "sql": "",
        "query_result": {},
        "sql_validation": {"ok": True, "reason": "skipped-sql"}
        if intent != "query_db"
        else {},
    }
    if answer:
        out["answer"] = answer
    return out

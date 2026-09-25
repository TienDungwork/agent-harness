"""LangGraph nodes cho guardrail — tên node chứa ``guardrail`` để trace/tối ưu từng bước."""

from __future__ import annotations

from typing import Any

from src.agent.node_io import node_event

AgentState = dict[str, Any]
from src.guardrails import (
    OUT_OF_SCOPE_REPLY,
    _is_tool_empty,
    check_input,
    check_output,
    in_scope,
    redact_pii,
)


def _question(state: AgentState) -> str:
    return (state.get("question") or "").strip()


def guardrail_input_node(state: AgentState) -> dict:
    q = _question(state)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    check_input(q)
    redacted = redact_pii(q)
    pii_found = redacted != q
    return {
        "question": redacted,
        "events": [node_event(
            "guardrail_input",
            input={"question": q},
            output={"question": redacted, "pii_redacted": pii_found, "ok": True},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }


def guardrail_scope_node(state: AgentState) -> dict:
    q = _question(state)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    scoped = in_scope(q)
    return {
        "guardrail_in_scope": scoped,
        "events": [node_event(
            "guardrail_scope",
            input={"question": q},
            output={"in_scope": scoped},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }


def guardrail_redact_node(state: AgentState) -> dict:
    q = _question(state)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    redacted = redact_pii(q)
    pii_found = redacted != q
    return {
        "question": redacted,
        "events": [node_event(
            "guardrail_redact",
            input={"question": q},
            output={"question": redacted, "pii_redacted": pii_found},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }


def guardrail_out_of_scope_node(state: AgentState) -> dict:
    q = _question(state)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    source = state.get("intent") or "out_of_scope"
    return {
        "answer": OUT_OF_SCOPE_REPLY,
        "respond_mode": "out_of_scope",
        "events": [node_event(
            "guardrail_out_of_scope",
            input={"question": q, "source": source},
            output={"answer": OUT_OF_SCOPE_REPLY, "respond_mode": "out_of_scope"},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }


def _build_output_evidence(state: AgentState, result: Any) -> list[str]:
    question = (state.get("question") or result.question or "").strip()
    query = result.query
    if not query:
        ev = [question] if question else []
        if state.get("respond_mode") in ("inline", "out_of_scope") or getattr(result, "detail", None) in ("chat", "clarify", "out_of_scope", "inline"):
            if getattr(result, "answer", None):
                ev.append(result.answer)
        return ev
    return [question] + (
        [f"row_count={query.row_count}", getattr(query, "reply_vi", "")]
        + [f"{c}={v}" for row in query.rows for c, v in zip(query.columns, row)]
    )


def guardrail_output_node(state: AgentState) -> dict:
    from src.agent.graph import Agent_Output

    result = state.get("result")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    if result is None:
        return {
            "events": [node_event(
                "guardrail_output",
                input={"question": _question(state)},
                output={"skipped": True, "reason": "no_result"},
                meta={"user_id": user_id, "session_id": session_id},
            )],
        }

    evidence = _build_output_evidence(state, result)
    tool_empty = _is_tool_empty(result.query)
    checked = check_output(result.answer, evidence, tool_empty=tool_empty)
    guarded = Agent_Output(
        question=result.question,
        answer=checked.answer,
        query=result.query,
        detail=result.detail,
    )
    return {
        "result": guarded,
        "events": [node_event(
            "guardrail_output",
            input={"question": result.question, "answer_len": len(result.answer or "")},
            output={
                "valid": checked.valid,
                "issues": checked.issues,
                "answer": checked.answer,
            },
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }

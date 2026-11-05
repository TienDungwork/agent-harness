"""Recall long-term memory và post-turn extract."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState, Agent_Output
from src.infra.monitoring.tracing import current_span, trace_step

def recall_node(state: AgentState) -> dict:
    from src.shared.config import settings
    from src.infra.memory.longterm import recall_long_term

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    with trace_step(
        current_span(),
        "recall_long_term",
        input={"user_id": user_id, "question_len": len(q)},
        as_type="retriever",
    ) as sub:
        if not settings.long_term_memory_enabled:
            sub["output"] = {"disabled": True, "recalled_count": 0}
            memories: list[str] = []
        else:
            memories = recall_long_term(user_id, q, k=3)
            sub["output"] = {"disabled": False, "recalled_count": len(memories)}
    if not settings.long_term_memory_enabled:
        return {
            "user_id": user_id,
            "session_id": session_id,
            "original_question": q,
            "recalled_memories": [],
            "intent": "",
            "answer": "",
            "respond_mode": "",
            "docs_answer": None,
            "orchestrator_plan": None,
            "orchestrator_step_index": 0,
            "orchestrator_step_results": [],
            "orchestrator_multi_active": False,
            "multi_hop_ready": False,
            "result": None,
            "rows": [],
            "columns": [],
            "sql": "",
            "error": "",
            "repair_count": 0,
            "chart_png_base64": "",
            "chart_spec": None,
            "chart_requested": False,
            "chart_type": None,
            "events": [node_event(
                "recall",
                input={"user_id": user_id, "question": q},
                output={"recalled_memories": [], "disabled": True},
                meta={"user_id": user_id, "session_id": session_id, "recalled_count": 0, "disabled": True},
            )],
        }
    ev_output: dict[str, Any] = {"recalled_memories": memories}
    ev_meta: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "recalled_count": len(memories),
    }
    return {
        "user_id": user_id,
        "session_id": session_id,
        "original_question": q,
        "recalled_memories": memories,
        "intent": "",
        "answer": "",
        "respond_mode": "",
        "docs_answer": None,
        "orchestrator_plan": None,
        "orchestrator_step_index": 0,
        "orchestrator_batch_sub_questions": [],
        "orchestrator_batch_end_index": 0,
        "orchestrator_step_results": [],
        "orchestrator_multi_active": False,
        "sql_batch": [],
        "sql_batch_results": [],
        "multi_hop_ready": False,
        "result": None,
        "rows": [],
        "columns": [],
        "sql": "",
        "error": "",
        "repair_count": 0,
        "chart_png_base64": "",
        "chart_spec": None,
        "chart_requested": False,
        "chart_type": None,
        "events": [node_event(
            "recall",
            input={"user_id": user_id, "question": q},
            output=ev_output,
            meta=ev_meta,
        )],
    }


# Alias node naming chuẩn hóa theo specs/implementation-plan.md
recall_memory_node = recall_node


def extract_memory_node(state: AgentState) -> dict:
    """Node trích xuất fact từ question và answer của state hiện tại và lưu vào PostgreSQL."""
    from src.shared.config import settings
    from src.infra.memory.extract import extract_and_store_memory, memory_detail_includes_answer

    if not settings.long_term_memory_enabled:
        return {"extracted_memories": []}

    uid = state.get("user_id") or "default"
    sid = state.get("session_id") or "default"
    q = state.get("question") or state.get("original_question") or ""
    res = state.get("result")
    ans = res.answer if res else (state.get("answer") or "")
    detail = res.detail if res else (state.get("respond_mode") or state.get("intent") or "")
    include_answer = memory_detail_includes_answer(detail)

    extracted = extract_and_store_memory(
        uid, q, ans if include_answer else "", detail=detail, include_answer=include_answer
    )

    return {
        "extracted_memories": extracted,
        "events": [node_event(
            "store_extract",
            input={"user_id": uid, "question": q, "include_answer": include_answer},
            output={"extracted_memories": extracted},
            meta={"user_id": uid, "session_id": sid, "extracted_count": len(extracted)},
        )],
    }


def run_store_extract(
    user_id: str,
    session_id: str,
    question: str,
    result: Agent_Output | None,
    parent_span: Any = None,
) -> list[dict]:
    """Post-pipeline: extract + store memory sau khi đã trả lời (không chặn respond)."""
    from src.shared.config import settings
    from src.infra.memory.extract import extract_and_store_memory, memory_detail_includes_answer

    if not settings.long_term_memory_enabled:
        return []

    q = question or ""
    uid = user_id or "default"
    sid = session_id or "default"
    res = result
    detail = res.detail if res else ""
    ans = res.answer if res else ""
    include_answer = memory_detail_includes_answer(detail)

    input_payload = {
        "user_id": uid,
        "question": q,
        "answer": ans,
        "detail": detail,
        "include_answer": include_answer,
    }

    import time
    t0 = time.perf_counter()
    with trace_step(
        parent_span,
        "store_extract",
        input=input_payload,
        metadata={"user_id": uid, "session_id": sid},
        as_type="chain",
    ) as step:
        extracted = extract_and_store_memory(
            uid, q, ans if include_answer else "", detail=detail, include_answer=include_answer
        )
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        ev = node_event(
            "store_extract",
            input=input_payload,
            output={"extracted_memories": extracted},
            meta={"user_id": uid, "session_id": sid, "extracted_count": len(extracted), "duration_ms": dur_ms},
        )
        step["input"] = ev["input"]
        step["output"] = ev["output"]
        step["metadata"] = ev["meta"]

    return [
        {"node_id": "store_extract", "status": "running"},
        {"node_id": "store_extract", "status": "done", "duration_ms": dur_ms, **{k: ev[k] for k in ("input", "output", "meta")}},
    ]

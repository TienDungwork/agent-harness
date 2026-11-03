"""Recall long-term memory và post-turn extract."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


from src.agent.node_io import node_event
from src.agent.state import AgentState, Agent_Output
from src.monitoring.tracing import trace_step

def recall_node(state: AgentState) -> dict:
    from src.config import settings
    from src.memory.longterm import recall_long_term

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    if not settings.long_term_memory_enabled:
        return {
            "user_id": user_id,
            "session_id": session_id,
            "original_question": q,
            "recalled_memories": [],
            "rewritten": None,
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
            "events": [node_event(
                "recall",
                input={"user_id": user_id, "question": q},
                output={"recalled_memories": [], "disabled": True},
                meta={"user_id": user_id, "session_id": session_id, "recalled_count": 0, "disabled": True},
            )],
        }
    try:
        memories = recall_long_term(user_id, q, k=3)
        ev_output: dict[str, Any] = {"recalled_memories": memories}
        ev_meta: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "recalled_count": len(memories),
        }
    except Exception as exc:
        logger.warning("recall_long_term failed, degrading safely: %s", exc)
        memories = []
        ev_output = {
            "recalled_memories": [],
            "degraded": True,
            "error": str(exc)[:200],
        }
        ev_meta = {
            "user_id": user_id,
            "session_id": session_id,
            "recalled_count": 0,
            "degraded": True,
        }
    return {
        "user_id": user_id,
        "session_id": session_id,
        "original_question": q,
        "recalled_memories": memories,
        "rewritten": None,
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
    from src.config import settings
    from src.memory.extract import extract_and_store_memory, memory_detail_includes_answer

    if not settings.long_term_memory_enabled:
        return {"extracted_memories": []}

    uid = state.get("user_id") or "default"
    sid = state.get("session_id") or "default"
    q = state.get("question") or state.get("original_question") or ""
    res = state.get("result")
    ans = res.answer if res else (state.get("answer") or "")
    detail = res.detail if res else (state.get("respond_mode") or state.get("intent") or "")
    include_answer = memory_detail_includes_answer(detail)

    try:
        extracted = extract_and_store_memory(
            uid, q, ans if include_answer else "", detail=detail, include_answer=include_answer
        )
    except Exception as exc:
        logger.warning("extract_memory_node failed, degrading safely: %s", exc)
        extracted = []

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
    from src.config import settings
    from src.memory.extract import extract_and_store_memory, memory_detail_includes_answer

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
        "answer": ans if include_answer else "",
        "detail": detail,
        "include_answer": include_answer,
    }

    import time
    t0 = time.perf_counter()
    try:
        with trace_step(
            parent_span,
            "store_extract",
            metadata={"user_id": uid, "session_id": sid},
        ) as step:
            try:
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
            except Exception as exc:
                dur_ms = round((time.perf_counter() - t0) * 1000, 1)
                logger.warning("extract_and_store_memory failed, degrading safely: %s", exc)
                err_msg = str(exc)[:200]
                ev = node_event(
                    "store_extract",
                    input=input_payload,
                    output={"extracted_memories": [], "degraded": True, "error": err_msg},
                    meta={"user_id": uid, "session_id": sid, "extracted_count": 0, "degraded": True, "duration_ms": dur_ms},
                )
            step["input"] = ev["input"]
            step["output"] = ev["output"]
            step["metadata"] = ev["meta"]

        return [
            {"node_id": "store_extract", "status": "running"},
            {"node_id": "store_extract", "status": "done", "duration_ms": dur_ms, **{k: ev[k] for k in ("input", "output", "meta")}},
        ]
    except Exception as exc:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.warning("run_store_extract failed, degrading safely: %s", exc)
        err_msg = str(exc)[:200]
        return [
            {"node_id": "store_extract", "status": "running"},
            {
                "node_id": "store_extract",
                "status": "done",
                "duration_ms": dur_ms,
                "input": input_payload,
                "output": {"extracted_memories": [], "degraded": True, "error": err_msg},
                "meta": {"user_id": uid, "session_id": sid, "extracted_count": 0, "degraded": True, "duration_ms": dur_ms},
            },
        ]

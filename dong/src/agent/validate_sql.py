"""Node validate_sql & repair_sql — kiểm tra và sửa câu lệnh text-to-SQL (Phase 3c)."""

from __future__ import annotations

from src.agent.generate_sql import extract_sql
from src.agent.sql_scope import apply_organization_scope
from src.agent.node_io import node_event
from src.config import settings
from src.db.validator import ValidationResult, validate_sql
from src.llm.client import invoke_text, use_offline_tools
from src.monitoring.tracing import trace_substep
from src.prompts import registry


def _trace_validate_sql(sql: str) -> ValidationResult:
    """Validate SQL và ghi substep Langfuse ``tool:validate_sql``."""
    with trace_substep("validate_sql", kind="tool", input={"sql": sql}) as sub:
        val = validate_sql(sql)
        sub["output"] = val.to_dict()
        return val


def validate_sql_node(state: dict) -> dict:
    """Validate SQL query against security and schema rules.

    Returns ``{"sql_validation": {...}, "events": [...]}``.
    """
    from src.agent.sql_batch import validate_sql_batch

    sql = state.get("sql") or ""
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    sql_batch = state.get("sql_batch") or []

    if len(sql_batch) >= 2:
        val_dict = validate_sql_batch(sql_batch)
        out: dict = {
            "sql_validation": val_dict,
            "events": [node_event(
                "validate_sql",
                input={"sql_batch": sql_batch},
                output=val_dict,
                meta={"user_id": user_id, "session_id": session_id, "ok": val_dict.get("ok"), "batch": True},
            )],
        }
        if not val_dict.get("ok") and not state.get("error"):
            out["error"] = val_dict.get("reason") or "batch_validation_failed"
        return out

    val = _trace_validate_sql(sql)
    val_dict = val.to_dict()

    out: dict = {
        "sql_validation": val_dict,
        "events": [
            node_event(
                "validate_sql",
                input={"sql": sql},
                output=val_dict,
                meta={
                    "user_id": user_id,
                    "session_id": session_id,
                    "ok": val.ok,
                },
            )
        ],
    }
    if not val.ok and not state.get("error"):
        out["error"] = val.reason
    return out


def repair_sql_node(state: dict) -> dict:
    """Repair SQL query using LLM or offline fallback when validation/execution fails.

    Returns ``{"sql": str, "repair_count": int, "events": [...]}``.
    """
    repair_count = int(state.get("repair_count") or 0)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    question = state.get("question", "")
    rewritten = state.get("rewritten")
    schema_excerpt = state.get("schema_excerpt", "")
    old_sql = state.get("sql") or ""
    sql_batch = state.get("sql_batch") or []

    if len(sql_batch) >= 2:
        from src.agent.sql_batch import build_sql_batch

        subs = [item.get("sub_question", "") for item in sql_batch]
        new_batch = build_sql_batch(subs)
        new_repair_count = repair_count + 1
        return {
            "sql_batch": new_batch,
            "sql": new_batch[0]["sql"] if new_batch else old_sql,
            "repair_count": new_repair_count,
            "error": "",
            "events": [node_event(
                "repair_sql",
                input={"sql_batch": sql_batch, "repair_count": repair_count},
                output={"sql_batch": new_batch, "repair_count": new_repair_count, "batch": True},
                meta={"user_id": user_id, "session_id": session_id},
            )],
        }

    if rewritten is not None:
        if hasattr(rewritten, "text"):
            q_text = rewritten.text or question
        elif isinstance(rewritten, dict):
            q_text = rewritten.get("text") or question
        else:
            q_text = question
    else:
        q_text = question

    max_repairs = settings.sql_repair_max
    if repair_count >= max_repairs:
        prev_err = state.get("error")
        err_msg = f"Đã vượt quá số lần sửa SQL tối đa ({max_repairs}). {prev_err}".strip() if prev_err else f"Đã vượt quá số lần sửa SQL tối đa ({max_repairs})."
        return {
            "sql": old_sql,
            "repair_count": repair_count,
            "error": err_msg,
            "events": [
                node_event(
                    "repair_sql",
                    input={"sql": old_sql, "repair_count": repair_count},
                    output={"sql": old_sql, "error": err_msg, "limit_exceeded": True},
                    meta={"user_id": user_id, "session_id": session_id, "max_repairs": max_repairs},
                )
            ],
        }

    new_repair_count = repair_count + 1

    if use_offline_tools():
        q_lower = q_text.lower()
        has_today = any(kw in q_lower for kw in ("hôm nay", "hom nay", "today"))
        if has_today:
            repaired_sql = "SELECT count(*) FROM plate_event WHERE event_time >= CURRENT_DATE"
        else:
            repaired_sql = "SELECT count(*) FROM plate_event"
        repaired_sql = apply_organization_scope(repaired_sql)
        return {
            "sql": repaired_sql,
            "repair_count": new_repair_count,
            "error": "",
            "events": [
                node_event(
                    "repair_sql",
                    input={"sql": old_sql, "repair_count": repair_count, "offline": True},
                    output={"sql": repaired_sql, "repair_count": new_repair_count},
                    meta={"user_id": user_id, "session_id": session_id, "offline": True},
                )
            ],
        }

    system_prompt = registry().render("sql_agent")
    val_reason = (state.get("sql_validation") or {}).get("reason") or state.get("error") or "Câu SQL không hợp lệ."

    with trace_substep("build_repair_prompt", kind="tool", input={"repair_count": repair_count}) as sub:
        user_parts: list[str] = [
            "Câu SQL trước bị từ chối hoặc chạy lỗi.",
            f"Lý do validation: {val_reason}",
        ]
        if state.get("error") and state.get("error") != val_reason:
            user_parts.append(f"Lỗi execute: {state.get('error')}")
        user_parts.append(f"SQL cũ:\n{old_sql}")
        user_parts.append(f"Câu hỏi:\n{q_text}")
        if schema_excerpt:
            user_parts.append(f"Schema excerpt:\n{schema_excerpt}")
        user_parts.append(
            "Hãy viết lại một câu SELECT hợp lệ. Chỉ dùng bảng và cột có trong schema excerpt; "
            "không gắn cột của bảng này vào bảng kia."
        )
        if settings.llm_backend == "self_hosted" or "qwen" in settings.model_name.lower():
            user_parts.insert(0, "/nothink")
        user_prompt = "\n\n".join(user_parts)
        sub["output"] = {"user_prompt_len": len(user_prompt), "reason": val_reason}

    max_tokens = settings.sql_generate_max_tokens

    raw = invoke_text(
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        substep="repair_sql",
    )

    with trace_substep("extract_sql", kind="tool", input={"raw_len": len(raw)}) as sub:
        repaired_sql = extract_sql(raw)
        sub["output"] = {"sql_len": len(repaired_sql), "empty": not bool(repaired_sql)}

    if not repaired_sql:
        err_msg = "Không thể sửa câu SQL từ phản hồi của mô hình."
        return {
            "sql": old_sql,
            "repair_count": new_repair_count,
            "error": err_msg,
            "events": [
                node_event(
                    "repair_sql",
                    input={"sql": old_sql, "repair_count": repair_count},
                    output={"sql": old_sql, "error": "empty_extract", "repair_count": new_repair_count},
                    meta={"user_id": user_id, "session_id": session_id, "max_tokens": max_tokens},
                )
            ],
        }

    with trace_substep("apply_org_scope", kind="tool", input={"sql": repaired_sql}) as sub:
        repaired_sql = apply_organization_scope(repaired_sql)
        sub["output"] = {"sql": repaired_sql}

    return {
        "sql": repaired_sql,
        "repair_count": new_repair_count,
        "error": "",
        "events": [
            node_event(
                "repair_sql",
                input={"sql": old_sql, "repair_count": repair_count},
                output={"sql": repaired_sql, "repair_count": new_repair_count},
                meta={"user_id": user_id, "session_id": session_id, "max_tokens": max_tokens},
            )
        ],
    }


def validate_and_repair_sql(
    sql: str,
    question: str,
    schema_excerpt: str = "",
    max_repairs: int | None = None,
    user_id: str = "default",
    session_id: str = "default",
) -> tuple[str, ValidationResult, int, list[dict]]:
    """Kiểm tra và sửa câu lệnh SQL nếu cần, lặp lại tối đa `max_repairs` lần.

    Dùng chung cho Graph pipeline, multi orchestrator, và các module khác.
    Trả về: (final_sql, ValidationResult, repair_count, events).
    """
    if max_repairs is None:
        max_repairs = settings.sql_repair_max

    cur_sql = (sql or "").strip()
    repair_count = 0
    events: list[dict] = []

    val = _trace_validate_sql(cur_sql)
    events.append(
        node_event(
            "validate_sql",
            input={"sql": cur_sql},
            output=val.to_dict(),
            meta={"user_id": user_id, "session_id": session_id, "ok": val.ok},
        )
    )

    while not val.ok and repair_count < max_repairs:
        rep_state = {
            "sql": cur_sql,
            "question": question,
            "schema_excerpt": schema_excerpt,
            "repair_count": repair_count,
            "sql_validation": val.to_dict(),
            "user_id": user_id,
            "session_id": session_id,
        }
        rep_out = repair_sql_node(rep_state)
        cur_sql = rep_out.get("sql") or cur_sql
        repair_count = rep_out.get("repair_count", repair_count + 1)
        events.extend(rep_out.get("events") or [])

        val = _trace_validate_sql(cur_sql)
        events.append(
            node_event(
                "validate_sql",
                input={"sql": cur_sql},
                output=val.to_dict(),
                meta={"user_id": user_id, "session_id": session_id, "ok": val.ok, "repair_attempt": repair_count},
            )
        )

    return cur_sql, val, repair_count, events

"""Node generate_sql — LLM text-to-SQL + extract SQL; max_tokens cap (Phase 3c)."""

from __future__ import annotations

import re

from src.agent.node_io import node_event
from src.agent.pre_sql import format_time_range_for_prompt, build_chart_sql_hint
from src.agent.sql_scope import apply_organization_scope, format_org_scope_for_prompt
from src.config import settings
from src.llm.client import invoke_text, use_offline_tools
from src.monitoring.tracing import trace_substep
from src.prompts import registry

# ── SQL extraction ────────────────────────────────────────────────────────────

_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_THINKING_BLOCK = re.compile(r"\x3cthink\x3e.*?\x3c/think\x3e", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Extract SQL from fenced ```sql block or bare text; strip trailing `;`."""
    raw = (text or "").strip()
    
    # 1. Try markdown fenced code block
    m = _SQL_FENCE.search(raw)
    if m:
        return m.group(1).strip().rstrip(";")

    # 2. Strip closed <think>...</think> blocks (Qwen3)
    cleaned = _THINKING_BLOCK.sub("", raw).strip()
    if cleaned:
        # Bare SQL starting with keyword
        if re.match(r"(?i)^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE)\b", cleaned):
            return cleaned.rstrip(";")

    # 3. Search for SELECT / WITH embedded in reasoning/think text
    sql_m = re.search(r"(?is)\b((?:SELECT|WITH)\s+[^\n;]+(?:\s+(?:FROM|WHERE|GROUP|ORDER|UNION|LIMIT)[^\n;]*)*)", raw)
    if sql_m:
        cand = sql_m.group(1).strip().rstrip(";")
        if re.search(r"(?i)\bFROM\b", cand) or re.search(r"(?i)\bSELECT\s+1\b", cand):
            return cand

    return ""


# ── Node ──────────────────────────────────────────────────────────────────────


def generate_sql_node(state: dict) -> dict:
    """Generate SQL from question + schema using LLM or offline fallback.

    Returns ``{sql, error, events}``; multi-hop batch thêm ``sql_batch``.
    """
    from src.agent.sql_batch import build_sql_batch, query_text_for_state

    question = state.get("question", "")
    schema_excerpt = state.get("schema_excerpt", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    batch_subs: list[str] = list(state.get("orchestrator_batch_sub_questions") or [])
    q_text = query_text_for_state(state)

    if len(batch_subs) >= 2:
        if use_offline_tools():
            sql_batch = build_sql_batch(batch_subs)
        else:
            system_prompt = registry().render("sql_agent")
            user_parts: list[str] = []
            rewritten = state.get("rewritten")
            time_range = None
            if rewritten is not None:
                if hasattr(rewritten, "time_range"):
                    time_range = rewritten.time_range
                elif isinstance(rewritten, dict):
                    time_range = rewritten.get("time_range")
            tr_hint = format_time_range_for_prompt(time_range)
            if tr_hint:
                user_parts.append(tr_hint)
            org_hint = format_org_scope_for_prompt()
            if org_hint:
                user_parts.append(org_hint)
            if schema_excerpt:
                user_parts.append(f"Schema excerpt:\n{schema_excerpt}")
            numbered = "\n".join(f"{i + 1}. {sq}" for i, sq in enumerate(batch_subs))
            user_parts.append(
                f"Các câu hỏi con (mỗi câu một SQL SELECT riêng, trả về đúng {len(batch_subs)} khối ```sql ... ``` theo thứ tự):\n{numbered}"
            )
            if settings.llm_backend == "self_hosted" or "qwen" in settings.model_name.lower():
                user_parts.insert(0, "/nothink")
            user_prompt = "\n\n".join(user_parts)
            raw = invoke_text(system_prompt, user_prompt, max_tokens=settings.sql_generate_max_tokens, substep="generate_sql")
            sql_batch = build_sql_batch(batch_subs, raw_llm=raw)
        first_sql = sql_batch[0]["sql"] if sql_batch else ""
        return {
            "sql": first_sql,
            "sql_batch": sql_batch,
            "error": "",
            "events": [node_event(
                "generate_sql",
                input={"batch_sub_questions": batch_subs, "schema_excerpt_len": len(schema_excerpt)},
                output={"sql_batch": sql_batch, "batch_size": len(sql_batch)},
                meta={"user_id": user_id, "session_id": session_id, "batch": True},
            )],
        }

    # ── Offline path ──────────────────────────────────────────────────────
    if use_offline_tools():
        q_lower = q_text.lower()
        has_today = any(kw in q_lower for kw in ("hôm nay", "hom nay", "today"))
        if any(kw in q_lower for kw in ("đám đông", "dam dong", "crowd")):
            sql = "SELECT count(*) FROM anomaly_event WHERE event_type = 'CROWD_DETECTION'"
        elif any(kw in q_lower for kw in ("leo trèo", "xâm nhập", "intrusion")):
            sql = "SELECT count(*) FROM anomaly_event WHERE event_type = 'INTRUSION_DETECTION'"
        elif any(kw in q_lower for kw in ("mực nước", "muc nuoc", "water_level")):
            sql = "SELECT count(*) FROM anomaly_event WHERE event_type = 'WATER_LEVEL_DETECTION'"
        elif any(kw in q_lower for kw in ("ẩu đả", "au da", "fight")):
            sql = "SELECT count(*) FROM anomaly_event WHERE event_type = 'FIGHT_DETECTION'"
        elif any(kw in q_lower for kw in ("cháy", "khói", "fire", "smoke")):
            sql = "SELECT count(*) FROM fire_smoke_event"
        elif has_today:
            sql = "SELECT count(*) FROM plate_event WHERE event_time >= CURRENT_DATE"
        else:
            sql = "SELECT count(*) FROM plate_event"
        sql = apply_organization_scope(sql)
        return {
            "sql": sql,
            "error": "",
            "events": [node_event(
                "generate_sql",
                input={"question": q_text, "offline": True},
                output={"sql": sql},
                meta={"user_id": user_id, "session_id": session_id, "offline": True},
            )],
        }

    # ── Online path ───────────────────────────────────────────────────────
    system_prompt = registry().render("sql_agent")
    rewritten = state.get("rewritten")

    with trace_substep("build_prompt", kind="tool", input={"question": q_text}) as sub:
        user_parts: list[str] = []
        time_range = None
        if rewritten is not None:
            if hasattr(rewritten, "time_range"):
                time_range = rewritten.time_range
            elif isinstance(rewritten, dict):
                time_range = rewritten.get("time_range")
        tr_hint = format_time_range_for_prompt(time_range)
        if tr_hint:
            user_parts.append(tr_hint)
        chart_hint = build_chart_sql_hint(q_text)
        if chart_hint:
            user_parts.append(chart_hint)
        org_hint = format_org_scope_for_prompt()
        if org_hint:
            user_parts.append(org_hint)
        if schema_excerpt:
            user_parts.append(f"Schema excerpt:\n{schema_excerpt}")
        user_parts.append(f"Câu hỏi:\n{q_text}")
        if settings.llm_backend == "self_hosted" or "qwen" in settings.model_name.lower():
            user_parts.insert(0, "/nothink")
        user_prompt = "\n\n".join(user_parts)
        sub["output"] = {"user_prompt_len": len(user_prompt), "schema_excerpt_len": len(schema_excerpt)}

    max_tokens = settings.sql_generate_max_tokens

    raw = invoke_text(
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        substep="generate_sql",
    )

    with trace_substep("extract_sql", kind="tool", input={"raw_len": len(raw)}) as sub:
        sql = extract_sql(raw)
        sub["output"] = {"sql_len": len(sql), "empty": not bool(sql)}

    if not sql:
        return {
            "sql": "",
            "error": "Không thể tạo câu SQL từ câu hỏi.",
            "events": [node_event(
                "generate_sql",
                input={"question": q_text, "schema_excerpt_len": len(schema_excerpt)},
                output={"sql": "", "error": "empty_extract", "raw_len": len(raw)},
                meta={
                    "user_id": user_id,
                    "session_id": session_id,
                    "max_tokens": max_tokens,
                },
            )],
        }

    with trace_substep("apply_org_scope", kind="tool", input={"sql": sql}) as sub:
        sql = apply_organization_scope(sql)
        sub["output"] = {"sql": sql}

    return {
        "sql": sql,
        "error": "",
        "events": [node_event(
            "generate_sql",
            input={"question": q_text, "schema_excerpt_len": len(schema_excerpt)},
            output={"sql": sql},
            meta={
                "user_id": user_id,
                "session_id": session_id,
                "max_tokens": max_tokens,
            },
        )],
    }

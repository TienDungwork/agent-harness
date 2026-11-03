"""Orchestrator node, routing, batch SQL prep."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


from src.agent.intent import is_stat_event_domain
from src.agent.node_io import node_event
from src.agent.state import AgentState
from src.llm.schemas import OrchestratorPlan, OrchestratorStep

def _is_multi_plan(plan: OrchestratorPlan | None) -> bool:
    return bool(plan and (plan.is_multi or len(plan.steps) >= 2))


def _reset_pipeline_fields() -> dict:
    return {
        "sql": "",
        "repair_count": 0,
        "error": "",
        "rows": [],
        "columns": [],
        "sql_validation": {},
        "params": [],
        "schema_excerpt": "",
        "selected_tables": [],
        "docs_answer": None,
        "respond_mode": "",
        "answer": "",
        "chart_png_base64": "",
        "chart_spec": None,
        "sql_batch": [],
        "sql_batch_results": [],
    }


def _batch_steps_from_plan(plan: OrchestratorPlan, start_idx: int) -> tuple[list[str], int, str]:
    """Gom các bước liên tiếp cùng agent; trả (sub_questions, end_idx, agent)."""
    steps = plan.steps
    if start_idx >= len(steps):
        return [], start_idx, ""
    agent = steps[start_idx].agent
    subs: list[str] = []
    i = start_idx
    while i < len(steps) and steps[i].agent == agent:
        subs.append(steps[i].sub_question)
        i += 1
    return subs, i, agent


def _apply_orchestrator_batch(out: dict, plan: OrchestratorPlan, start_idx: int) -> None:
    subs, end_idx, agent = _batch_steps_from_plan(plan, start_idx)
    out["orchestrator_batch_sub_questions"] = subs
    out["orchestrator_batch_end_index"] = end_idx
    if subs:
        out["question"] = subs[0]
    out.setdefault("events", [])
    if out["events"]:
        out["events"][-1].setdefault("meta", {})["batch_agent"] = agent
        out["events"][-1]["meta"]["batch_size"] = len(subs)


def orchestrator_node(state: AgentState) -> dict:
    from src.agent.orchestrator import plan_orchestration
    from src.llm.client import use_offline_tools

    q = state.get("question", "")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else q
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    intent = state.get("intent", "query_data")
    llm_used = not use_offline_tools()

    plan_existing: OrchestratorPlan | None = state.get("orchestrator_plan")
    if state.get("orchestrator_multi_active") and plan_existing and plan_existing.steps:
        idx = int(state.get("orchestrator_step_index") or 0)
        subs, end_idx, agent = _batch_steps_from_plan(plan_existing, idx)
        out = {
            **_reset_pipeline_fields(),
            "orchestrator_batch_sub_questions": subs,
            "orchestrator_batch_end_index": end_idx,
            "events": [node_event(
                "orchestrator",
                input={"question": q_text, "dispatch_from": idx, "batch_sub_questions": subs},
                output={"agent": agent, "batch_size": len(subs), "batch_end_index": end_idx},
                meta={"user_id": user_id, "session_id": session_id, "is_multi": True},
            )],
        }
        if subs:
            out["question"] = subs[0]
        return out

    sub_questions = list(getattr(rewritten, "sub_questions", None) or [])
    original_q = state.get("original_question") or q

    from src.agent.orchestrator import is_multi_question
    # Fast pass-through nếu là câu đơn, tránh gọi LLM lần 2
    if not is_multi_question(q_text, rewritten=rewritten, original=original_q, intent=intent):
        if is_stat_event_domain(q_text):
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="query_data", sub_question=q_text)], is_multi=False, reason="Fast passthrough: stat domain")
        elif intent == "out_of_scope":
            plan = OrchestratorPlan(steps=[], is_multi=False, reason="Fast passthrough: out_of_scope")
        elif intent in ("how_to", "troubleshoot", "concept"):
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="docs", sub_question=q_text)], is_multi=False, reason="Fast passthrough: docs")
        elif intent in ("chat", "clarify"):
            plan = OrchestratorPlan(steps=[], is_multi=False, reason="Fast passthrough: inline")
        else:
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="query_data", sub_question=q_text)], is_multi=False, reason="Fast passthrough: query_data")
        llm_used = False
    elif intent == "out_of_scope" and is_stat_event_domain(q_text):
        plan = plan_orchestration(
            q_text, sub_questions=sub_questions, original=original_q, intent=intent,
        )
    elif intent == "out_of_scope":
        plan = OrchestratorPlan(steps=[], is_multi=False, reason="out_of_scope")
    else:
        plan = plan_orchestration(
            q_text, sub_questions=sub_questions, original=original_q, intent=intent,
        )

    out: dict = {
        "orchestrator_plan": plan,
        "events": [node_event(
            "orchestrator",
            input={"question": q_text, "intent": intent, "sub_questions": sub_questions},
            output={"orchestrator_plan": plan.model_dump()},
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }
    if _is_multi_plan(plan):
        out.update({
            "orchestrator_multi_active": True,
            "orchestrator_step_index": 0,
            "orchestrator_step_results": [],
            "multi_hop_ready": False,
            **_reset_pipeline_fields(),
        })
        _apply_orchestrator_batch(out, plan, 0)
        out["events"][0]["meta"]["is_multi"] = True
    return out


def route_orchestrator(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else state.get("question", "")

    plan: OrchestratorPlan | None = state.get("orchestrator_plan")
    if state.get("orchestrator_multi_active") and plan and plan.steps:
        idx = int(state.get("orchestrator_step_index") or 0)
        if idx >= len(plan.steps):
            return "respond"
        batch = state.get("orchestrator_batch_sub_questions") or []
        if batch:
            agent = plan.steps[idx].agent
        else:
            agent = plan.steps[idx].agent
        return "query_data" if agent == "query_data" else "docs"

    if is_stat_event_domain(q_text):
        return "query_data"

    if intent == "out_of_scope":
        return "out"

    if plan and plan.steps:
        agent = plan.steps[0].agent
        if agent == "docs":
            return "docs"
        elif agent == "query_data":
            return "query_data"

    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    return "query_data"



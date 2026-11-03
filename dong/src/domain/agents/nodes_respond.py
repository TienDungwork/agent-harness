"""Final respond node — stat, docs, multi-hop."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


from src.domain.agents.graph_runtime import emit_answer_chunks
from src.domain.agents.node_io import node_event
from src.domain.agents.state import AgentState, Agent_Output
from src.infra.chart.render import _detect_chart_type, plan_chart, should_render_chart
from src.shared.guardrails import OUT_OF_SCOPE_REPLY
from src.infra.llm.schemas import QueryResult, StatAnswer
from src.domain.agents.graph_helpers import (
    effective_question,
    filter_memories_for_stat,
    memory_context_block,
    original_question,
    respond_event_input,
    strip_thinking,
)
from src.domain.agents.nodes_orchestrator_synth import (
    _aggregate_all_events_rows,
    _build_orchestrator_query_result,
    _synthesize_orchestrator_answer,
)
from src.infra.monitoring.tracing import trace_substep


def respond_node(state: AgentState) -> dict:
    q_original = original_question(state)
    q = effective_question(state)
    error = state.get("error")
    rows = state.get("rows", [])
    columns = state.get("columns", [])
    chart_png = state.get("chart_png_base64") or ""
    plan = state.get("orchestrator_plan")
    step_results = state.get("orchestrator_step_results") or []
    respond_mode = state.get("respond_mode") or ""
    intent = state.get("intent", "query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    is_multi_respond = bool(
        state.get("multi_hop_ready")
        and step_results
        and plan
        and (getattr(plan, "is_multi", False) or len(getattr(plan, "steps", []) or []) >= 2)
    )

    from src.domain.agents.simple_answer import try_format_simple_answer
    from src.shared.config import settings
    from src.infra.llm.client import invoke_text, use_offline_tools

    answer_source = "template"
    llm_used = False
    q_low = q.lower()

    if respond_mode == "inline":
        ans = (state.get("answer") or "").strip()
        if not ans and intent == "chat":
            ans = "Chào bạn! Tôi là trợ lý AI giám sát camera VMS KCN Hưng Phú. Tôi có thể hỗ trợ gì cho bạn về dữ liệu camera, sự kiện hoặc hướng dẫn sử dụng hệ thống?"
        detail = intent or "chat"
        result = Agent_Output(question=q_original, answer=ans, detail=detail)
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=respond_event_input(state, respond_mode="inline", intent=intent),
                output={"answer_vi": ans, "answer_source": "inline"},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    if respond_mode == "out_of_scope":
        ans = (state.get("answer") or "").strip() or OUT_OF_SCOPE_REPLY
        result = Agent_Output(question=q_original, answer=ans, detail="out_of_scope")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=respond_event_input(state, respond_mode="out_of_scope"),
                output={"answer_vi": ans, "answer_source": "out_of_scope"},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    if is_multi_respond:
        from src.domain.agents.orchestrator import is_all_events_plan

        ans, answer_source = _synthesize_orchestrator_answer(q, step_results, state)
        check_q = f"{q} {q_original}".lower()
        if any(k in check_q for k in ("chỗ", "cho ngoi", "5 chỗ", "7 chỗ", "9 chỗ", "16 chỗ", "29 chỗ", "40 chỗ", "45 chỗ")):
            if "không có thông tin số chỗ ngồi" not in ans.lower():
                ans = f"{ans}\n(Lưu ý: Hệ thống chỉ phân loại 4 nhóm phương tiện CAR, MOTORCYCLE, TRUCK, BUS, không có thông tin số chỗ ngồi.)"
        llm_used = answer_source == "llm_text"
        agg_columns, agg_rows = _aggregate_all_events_rows(step_results) if is_all_events_plan(plan) else ([], [])
        if agg_rows:
            query_res = QueryResult(
                tool="sql_builder",
                columns=agg_columns,
                rows=[[r["domain"], r["count"]] for r in agg_rows],
                row_count=len(agg_rows),
                error="",
                reply_vi=ans,
            )
        else:
            query_res = _build_orchestrator_query_result(step_results, ans)

        chart_rows = agg_rows if agg_rows else []
        chart_spec = None
        if should_render_chart(q) and len(chart_rows) >= 2 and not chart_png:
            try:
                c_type = state.get("chart_type") or _detect_chart_type(q)
                chart_spec = plan_chart(chart_rows, q, chart_type=c_type)
                import src.domain.agents.graph as graph_mod

                chart_png = graph_mod.render_chart(chart_rows, chart_spec) or ""
            except Exception:
                chart_png = ""
                chart_spec = None

        if chart_png and len(chart_rows) > 1 and should_render_chart(q):
            ans = f"{ans} Biểu đồ phân bố theo loại sự kiện ({len(chart_rows)} nhóm)."
            answer_source = "chart_template" if answer_source == "template_all_events" else answer_source

        stat = StatAnswer(
            answer_vi=ans,
            highlights=[],
            chart_requested=should_render_chart(q) or bool(chart_png),
        )
        ans = stat.answer_vi
        result = Agent_Output(question=q_original, answer=ans, query=query_res, detail="orchestrator:multi")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        chart_meta = chart_spec.model_dump() if chart_spec else {}
        return {
            "result": result,
            "chart_png_base64": chart_png,
            "events": [node_event(
                "respond",
                input=respond_event_input(
                    state,
                    respond_mode="multi",
                    orchestrator_step_results=step_results,
                    step_count=len(step_results),
                ),
                output={
                    "answer_vi": ans,
                    "answer_source": answer_source,
                    "stat_answer": stat.model_dump(),
                    "query": query_res.model_dump(),
                },
                chart_png_base64=chart_png,
                chart_meta=chart_meta,
                chart_spec=chart_meta,
                meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id, "is_multi": True},
            )],
        }

    if respond_mode == "docs":
        docs_payload = state.get("docs_answer") or {}
        ans = (state.get("answer") or docs_payload.get("answer_vi") or "").strip()
        if not ans:
            ans = "Không tìm thấi tài liệu hướng dẫn phù hợp."
        result = Agent_Output(question=q_original, answer=ans, detail="docs")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=respond_event_input(state, respond_mode="docs"),
                output={"answer_vi": ans, "docs_answer": docs_payload},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    from src.domain.agents.camera_registry import (
        is_camera_count_query,
        is_camera_list_query,
        format_camera_count_answer,
        format_camera_list_answer,
    )

    if is_camera_count_query(q):
        ans, rows, columns = format_camera_count_answer()
        answer_source = "master_registry"
    elif is_camera_list_query(q) or (
        "danh sách" in q_low and "camera" in q_low and any(k in q_low for k in ("khu vực", "hợp lệ", "hiện có", "tất cả"))
    ):
        ans, rows, columns = format_camera_list_answer()
        answer_source = "master_registry"
    elif error:
        ans = f"Lỗi khi truy vấn: {error}"
        answer_source = "error"
    elif not rows:
        from src.shared.guardrails import empty_stat_reply

        ans = empty_stat_reply(q)
        answer_source = "empty"
    else:
        with trace_substep("simple_answer", kind="tool", input={"row_count": len(rows)}) as sub:
            simple_ans = try_format_simple_answer(q, rows)
            sub["output"] = {"matched": simple_ans is not None}
        if chart_png and len(rows) > 1 and should_render_chart(q):
            label = (columns[0] if columns else "dữ liệu").replace("_", " ")
            ans = f"Biểu đồ phân bố theo {label} ({len(rows)} nhóm)."
            answer_source = "chart_template"
            llm_used = False
        elif simple_ans is not None:
            ans = simple_ans
            if chart_png:
                ans = f"{ans} Biểu đồ đã tạo từ kết quả truy vấn."
            answer_source = "template_simple"
            llm_used = False
        else:
            lines = [", ".join(f"{c}={r[c]}" for c in columns) for r in rows[:20]]
            template_ans = f"Kết quả ({len(rows)} dòng):\n" + "\n".join(lines)
            ans = template_ans

            # Nén kết quả bảng SQL nếu vượt ngưỡng 300 tokens
            from src.infra.memory.context import compress_tool_result
            if len(template_ans) > 300 * 4:
                template_ans = compress_tool_result(template_ans, query=q, max_tokens=300)
                ans = template_ans

            if not use_offline_tools():
                llm_used = True
                try:
                    safety_instruction = (
                        "Tuân thủ nghiêm ngặt quy tắc an toàn VMS KCN Hưng Phú: "
                        "Không suy diễn số liệu ngoài dữ liệu truy vấn."
                    )
                    sys_prompt = registry().render("respond_stat")
                    sys_prompt = f"{sys_prompt}\n\n[Nhắc lại chỉ dẫn]: {safety_instruction}"

                    with trace_substep("respond_stat", kind="agent", input={"row_count": len(rows)}):
                        raw = invoke_text(
                            sys_prompt,
                            (
                                f"{memory_context_block(state, for_stat=True, question=q)}"
                                f"Câu hỏi: {q}\nDữ liệu:\n{template_ans}"
                            ),
                            max_tokens=settings.sql_respond_max_tokens,
                            substep=None,
                        )
                    polished = strip_thinking(raw)
                    if polished:
                        ans = polished
                        answer_source = "llm_text"
                except Exception as exc:
                    answer_source = f"template_fallback:{type(exc).__name__}"


    check_q = f"{q} {q_original}".lower()
    if any(k in check_q for k in ("chỗ", "cho ngoi", "5 chỗ", "7 chỗ", "9 chỗ", "16 chỗ", "29 chỗ", "40 chỗ", "45 chỗ")):
        if "không có thông tin số chỗ ngồi" not in ans.lower():
            ans = f"{ans}\n(Lưu ý: Hệ thống chỉ phân loại 4 nhóm phương tiện CAR, MOTORCYCLE, TRUCK, BUS, không có thông tin số chỗ ngồi.)"


    stat = StatAnswer(
        answer_vi=ans,
        highlights=[],
        chart_requested=should_render_chart(q) or bool(state.get("chart_png_base64")),
    )
    ans = stat.answer_vi

    query_res = QueryResult(
        tool="sql_builder",
        columns=columns,
        rows=[[r[c] for c in columns] for r in rows] if rows else [],
        row_count=len(rows) if rows else 0,
        error=error or "",
        reply_vi=ans
    )
    
    result = Agent_Output(question=q_original, answer=ans, query=query_res, detail="query_data")
    emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
    return {
        "result": result,
        "events": [node_event(
            "respond",
            input=respond_event_input(
                state,
                respond_mode="stat",
                columns=columns,
                rows=rows,
                row_count=len(rows),
                recalled_memories=filter_memories_for_stat(
                    state.get("recalled_memories") or [], q
                ),
                error=error or "",
            ),
            output={
                "answer_vi": ans,
                "answer_source": answer_source,
                "stat_answer": stat.model_dump(),
                "query": query_res.model_dump(),
            },
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }

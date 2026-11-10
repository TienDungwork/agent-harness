"""Chat, ask, SSE stream — AgentTurnService + LangGraph."""
from __future__ import annotations
import inspect
import json
import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from src.application.agent_turn import AgentTurnService, TurnInput, build_cache_data_from_output, detail_payload_from_cache, store_turn_cache
from src.api.helpers.auth import get_access_context
from src.api.helpers.errors import format_error_message
from src.api.models.schemas import AskRequest, AskResponse, ChatRequest, ChatResponse
from src.api.helpers.session_helpers import build_agent_trace, persist_session_turn
from src.api.helpers.sse_helpers import build_chart_sse_event, sanitize_sse_event
from src.domain.agents.graph import Agent_Input
from src.domain.authz.access_context import AccessContext
from src.shared.guardrails import GuardrailViolation, check_input, redact_pii
logger = logging.getLogger(__name__)
router = APIRouter(tags=['agent'])
_turn = AgentTurnService()


def _cache_from_turn(turn) -> dict[str, Any]:
    query = turn.query
    return {'question': turn.question, 'answer': turn.answer, 'tool': getattr(query, 'tool', '') if query else '', 'columns': getattr(query, 'columns', []) if query else [], 'rows': getattr(query, 'rows', []) if query else [], 'row_count': getattr(query, 'row_count', 0) if query else 0, 'agent_detail': (turn.detail or {})['agent_detail'] if 'agent_detail' in (turn.detail or {}) else ''}

@router.post('/api/chat', response_model=ChatResponse, tags=['agent'])
def chat(req: ChatRequest, request: Request, access: Annotated[AccessContext, Depends(get_access_context)]) -> ChatResponse:
    """Endpoint chính nhận câu hỏi từ Frontend UI."""
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=400, detail='session_id không được để trống.')
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail='user_id không được để trống.')
    request.state.user_id = req.user_id.strip()
    uid = access.user_id if access.user_id and access.user_id != 'default' else req.user_id.strip()
    redact_pii(req.question)
    raw_question = req.question.strip()
    import src.main as main_mod
    cached = main_mod._lookup_ttl_cache(raw_question)
    if cached:
        detail_payload = detail_payload_from_cache(cached)
        persist_session_turn(session_id=req.session_id.strip(), user_id=uid, question=(cached['question'] if 'question' in cached else None) or raw_question, answer=(cached['answer'] if 'answer' in cached else None) or '', detail=detail_payload)
        return ChatResponse(question=(cached['question'] if 'question' in cached else None) or raw_question, answer=(cached['answer'] if 'answer' in cached else None) or '', tool=(detail_payload['tool'] if 'tool' in detail_payload else None) or '', detail=detail_payload, row_count=int((detail_payload['row_count'] if 'row_count' in detail_payload else None) or 0))
    try:
        turn = _turn.process(TurnInput(question=raw_question, user_id=uid, session_id=req.session_id.strip(), access_context=access), trace_name='chat', trace_metadata={'endpoint': '/api/chat', 'provider': req.model_provider, 'session_id': req.session_id, 'user_id': uid, 'trace_question': req.question, 'role_group': access.role_group})
    except GuardrailViolation:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=format_error_message(exc)) from exc
    detail_payload = dict(turn.detail or {})
    persist_session_turn(session_id=req.session_id.strip(), user_id=uid, question=turn.question or raw_question, answer=turn.answer, detail=detail_payload)
    store_turn_cache(raw_question, turn.question or raw_question, (detail_payload['agent_detail'] if 'agent_detail' in detail_payload else None) or 'query_data', _cache_from_turn(turn))
    query = turn.query
    return ChatResponse(question=turn.question, answer=turn.answer, tool=getattr(query, 'tool', '') if query else '', detail=detail_payload, row_count=int(getattr(query, 'row_count', 0) or 0) if query else 0)

@router.post('/ask', response_model=AskResponse, tags=['agent'])
def ask(req: AskRequest, access: Annotated[AccessContext, Depends(get_access_context)]) -> AskResponse:
    """Endpoint tương thích ngược cho /ask."""
    redact_pii(req.question)
    raw_question = req.question.strip()
    uid = access.user_id if access.user_id and access.user_id != 'default' else (getattr(req, 'user_id', None) or 'default')
    import src.main as main_mod
    cached = main_mod._lookup_ttl_cache(raw_question)
    if cached:
        return AskResponse(question=(cached['question'] if 'question' in cached else None) or raw_question, answer=(cached['answer'] if 'answer' in cached else None) or '', tool=(cached['tool'] if 'tool' in cached else None) or '', columns=list((cached['columns'] if 'columns' in cached else None) or []), rows=list((cached['rows'] if 'rows' in cached else None) or []), row_count=int((cached['row_count'] if 'row_count' in cached else None) or 0))
    try:
        turn = _turn.process(TurnInput(question=raw_question, user_id=uid, session_id=getattr(req, 'session_id', None) or 'default', access_context=access), trace_name='ask', trace_metadata={'endpoint': '/ask', 'session_id': getattr(req, 'session_id', 'default'), 'user_id': uid, 'trace_question': req.question, 'role_group': access.role_group})
    except GuardrailViolation:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=format_error_message(exc)) from exc
    store_turn_cache(raw_question, turn.question or raw_question, ((turn.detail or {})['agent_detail'] if 'agent_detail' in (turn.detail or {}) else None) or 'query_data', _cache_from_turn(turn))
    query = turn.query
    return AskResponse(question=turn.question, answer=turn.answer, tool=getattr(query, 'tool', '') if query else '', columns=list(getattr(query, 'columns', []) or []) if query else [], rows=list(getattr(query, 'rows', []) or []) if query else [], row_count=int(getattr(query, 'row_count', 0) or 0) if query else 0)

@router.post('/api/agent/stream', tags=['agent'])
def stream_agent(req: ChatRequest, request: Request, access: Annotated[AccessContext, Depends(get_access_context)]) -> StreamingResponse:
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=400, detail='session_id không được để trống.')
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail='user_id không được để trống.')
    check_input(req.question)
    request.state.user_id = req.user_id.strip()
    uid = access.user_id if access.user_id and access.user_id != 'default' else req.user_id.strip()

    def event_generator():
        question = redact_pii(req.question)
        raw_question = req.question.strip()
        last_stream_error = ''
        got_final = False
        try:
            import src.main as main_mod
            cached = main_mod._lookup_ttl_cache(raw_question)
            if cached:
                detail_payload = detail_payload_from_cache(cached)
                ans = (cached['answer'] if 'answer' in cached else None) or ''
                yield f"data: {json.dumps({'node': 'cache', 'node_id': 'cache', 'status': 'done', 'output': ans}, ensure_ascii=False)}\n\n"
                persist_session_turn(session_id=req.session_id.strip(), user_id=uid, question=(cached['question'] if 'question' in cached else None) or raw_question, answer=ans, detail=detail_payload)
                yield f"data: {json.dumps({'complete': True, 'question': (cached['question'] if 'question' in cached else None) or raw_question, 'answer': ans, 'detail': detail_payload, 'node_id': '__answer__', 'status': 'done', 'output': ans}, ensure_ascii=False)}\n\n"
                return
            stream_kwargs: dict[str, Any] = {'trace_name': 'chat', 'trace_metadata': {'endpoint': '/api/agent/stream', 'provider': req.model_provider, 'session_id': req.session_id, 'user_id': uid, 'trace_question': req.question, 'role_group': access.role_group}, 'session_id': req.session_id, 'user_id': uid}
            target_fn = getattr(main_mod.run_agent_stream, 'side_effect', None) or main_mod.run_agent_stream
            if callable(target_fn):
                try:
                    sig = inspect.signature(target_fn)
                    if 'session_id' not in sig.parameters and (not any((p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()))):
                        stream_kwargs.pop('session_id', None)
                    if 'user_id' not in sig.parameters and (not any((p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()))):
                        stream_kwargs.pop('user_id', None)
                except (ValueError, TypeError):
                    pass
            last_chart_png: str | None = None
            last_chart_url: str | None = None
            last_chart_spec: dict[str, Any] | None = None
            last_chart_type: str | None = None
            last_chart_rows: list[dict] | None = None
            stream_trace_nodes: list[dict[str, Any]] = []
            for event in main_mod.run_agent_stream(Agent_Input(question=req.question.strip(), user_id=uid, stream_tokens=req.stream_tokens, access_context=access), **stream_kwargs):
                if '__final_result__' in event:
                    got_final = True
                    out = event['__final_result__']
                    query = getattr(out, 'query', None)
                    detail_payload: dict[str, Any] = {'tool': getattr(query, 'tool', '') if query else '', 'columns': getattr(query, 'columns', []) if query else [], 'row_count': getattr(query, 'row_count', 0) if query else 0, 'agent_detail': out.detail}
                    if last_chart_png or last_chart_url:
                        detail_payload['chart_type'] = last_chart_type or 'bar'
                        detail_payload['chart_spec'] = last_chart_spec or {}
                        if last_chart_rows is not None:
                            detail_payload['chart_rows'] = last_chart_rows
                        if last_chart_url:
                            detail_payload['chart_url'] = last_chart_url
                    chart_payload = None
                    if last_chart_png or last_chart_url or ('chart_spec' in detail_payload and detail_payload['chart_spec']):
                        chart_payload = {'png': last_chart_png, 'url': last_chart_url, 'spec': detail_payload['chart_spec'] if 'chart_spec' in detail_payload else None, 'type': detail_payload['chart_type'] if 'chart_type' in detail_payload else 'bar', 'rows': detail_payload['chart_rows'] if 'chart_rows' in detail_payload else None}
                    agent_trace = build_agent_trace(stream_trace_nodes, detail_payload)
                    persist_session_turn(session_id=req.session_id.strip(), user_id=uid, question=out.question or question, answer=out.answer, detail=detail_payload, chart=chart_payload, agent_trace=agent_trace)
                    detail_payload['agent_trace'] = agent_trace
                    store_turn_cache(raw_question, out.question or raw_question, out.detail or 'query_data', build_cache_data_from_output(out))
                    yield f"data: {json.dumps({'complete': True, 'question': out.question or question, 'answer': out.answer, 'detail': detail_payload, 'node_id': '__answer__', 'status': 'done', 'output': out.answer}, ensure_ascii=False)}\n\n"
                    continue
                event_node = event['node_id'] if 'node_id' in event else ''
                if event_node == 'error':
                    last_stream_error = str((event['output'] if 'output' in event else None) or last_stream_error or 'Agent error')
                if event_node and event_node not in ('__answer__', '__chart__', 'error'):
                    stream_trace_nodes.append({'node_id': event_node, 'status': event['status'] if 'status' in event else None, 'input': event['input'] if 'input' in event else None, 'output': event['output'] if 'output' in event else None, 'meta': event['meta'] if 'meta' in event else None, 'duration_ms': event['duration_ms'] if 'duration_ms' in event else None})
                event_chart_png = (event['chart_png_base64'] if 'chart_png_base64' in event else None) or ''
                event_chart_url = (event['chart_url'] if 'chart_url' in event else None) or ''
                event_chart_spec = event['chart_spec'] if 'chart_spec' in event else None
                if event_node == 'render_chart' and (event_chart_png or event_chart_url):
                    spec_dict = event_chart_spec if isinstance(event_chart_spec, dict) else {}
                    last_chart_png = event_chart_png or None
                    last_chart_url = event_chart_url or None
                    last_chart_spec = spec_dict
                    last_chart_type = (spec_dict['chart_type'] if 'chart_type' in spec_dict else 'bar') if spec_dict else 'bar'
                    event_input = (event['input'] if 'input' in event else None) or {}
                    raw_rows = (event_input['rows'] if 'rows' in event_input else None) if isinstance(event_input, dict) else None
                    if raw_rows is None:
                        raw_rows = event['rows'] if 'rows' in event else None
                    last_chart_rows = raw_rows if isinstance(raw_rows, list) else None
                    chart_sse = build_chart_sse_event(spec_dict, event_chart_png, last_chart_rows, chart_url=event_chart_url or None)
                    yield f'data: {json.dumps(chart_sse, ensure_ascii=False)}\n\n'
                try:
                    payload = json.dumps(sanitize_sse_event(event), ensure_ascii=False, default=str)
                except Exception as ser_exc:
                    friendly_msg = format_error_message(ser_exc)
                    yield f"data: {json.dumps({'node_id': 'error', 'status': 'done', 'output': friendly_msg}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'node_id': '__answer__', 'status': 'error', 'output': friendly_msg, 'detail': {'status': 'error'}}, ensure_ascii=False)}\n\n"
                    break
                yield f'data: {payload}\n\n'
            if not got_final and last_stream_error:
                logger.warning('Stream incomplete: %s', last_stream_error)
        except Exception as exc:
            friendly_msg = format_error_message(exc)
            yield f"data: {json.dumps({'node_id': 'error', 'status': 'done', 'output': friendly_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'node_id': '__answer__', 'status': 'error', 'output': friendly_msg, 'detail': {'status': 'error'}}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type='text/event-stream')

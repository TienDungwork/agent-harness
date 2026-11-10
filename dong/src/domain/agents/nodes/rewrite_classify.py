"""Rewrite, classify, inline respond."""
from __future__ import annotations
import logging
from typing import Any
logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage
from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState
from src.shared.config import settings
from src.infra.monitoring.tracing import current_span, trace_step

def rewrite_node(state: AgentState) -> dict:
    from src.domain.agents.nodes.intent import is_chat_greeting
    q = state['question'] if 'question' in state else ''
    user_id = state['user_id'] if 'user_id' in state else None
    session_id = state['session_id'] if 'session_id' in state else None
    rewritten = state['rewritten'] if 'rewritten' in state else None
    is_chat = is_chat_greeting(q)
    from src.domain.agents.nodes.rewrite import _needs_rewrite_llm
    from src.infra.memory.context import sliding_window, should_compact, create_compaction_diff
    raw_messages = list((state['messages'] if 'messages' in state else None) or [])
    max_msgs = getattr(settings, 'memory_max_messages', 20)
    if len(raw_messages) > max_msgs:
        with trace_step(current_span(), 'sliding_window', input={'message_count': len(raw_messages), 'max_messages': max_msgs}, as_type='tool') as sub:
            raw_messages = sliding_window(raw_messages, max_messages=max_msgs)
            sub['output'] = {'message_count': len(raw_messages)}
    diff_messages: list[Any] = []
    window_tokens = getattr(settings, 'memory_context_window_tokens', 4000)
    compact_threshold = getattr(settings, 'memory_compact_threshold', 0.4)
    if raw_messages and should_compact(raw_messages, window_tokens=window_tokens, threshold=compact_threshold):
        with trace_step(current_span(), 'compact_history', input={'message_count': len(raw_messages)}, as_type='tool') as sub:
            compaction_diff = create_compaction_diff(raw_messages, keep_recent=6)
            if compaction_diff and 'messages' in compaction_diff:
                diff_messages = compaction_diff['messages']
            sub['output'] = {'diff_count': len(diff_messages)}
    skip_llm = is_chat or (not raw_messages and (not _needs_rewrite_llm(q.strip())))
    llm_used = not skip_llm
    if not rewritten:
        import src.domain.agents.graph as graph_mod
        from src.infra.session import get_session_messages
        session_msgs = get_session_messages(session_id=session_id or 'default', user_id=user_id or 'default') or []
        rewrite_history: list[Any] = [m.model_dump() if hasattr(m, 'model_dump') else m for m in session_msgs] if session_msgs else raw_messages
        with trace_step(current_span(), 'rewrite_question', input={'question': q}, as_type='tool') as sub:
            rewritten = graph_mod.rewrite_question(q, history=rewrite_history)
            sub['output'] = {'text_len': len(rewritten.text or ''), 'sub_question_count': len(rewritten.sub_questions or [])}
    return {'rewritten': rewritten, 'question': rewritten.text, 'messages': diff_messages + [HumanMessage(q)], 'events': [node_event('rewrite', input={'question': q}, output={'rewritten': rewritten.model_dump()}, meta={'llm_used': llm_used, 'user_id': user_id, 'session_id': session_id, 'sub_question_count': len(rewritten.sub_questions or []), **({'skipped': True} if skip_llm else {})})]}

def classify_node(state: AgentState) -> dict:
    from src.infra.llm.client import use_offline_tools
    rewritten = state['rewritten']
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    llm_used = not use_offline_tools()
    import src.domain.agents.graph as graph_mod
    with trace_step(current_span(), 'classify_intent', input={'rewritten_text': rewritten.text}, as_type='tool') as sub:
        res = graph_mod.sanitize_intent_result(graph_mod.classify_intent_safe(rewritten))
        sub['output'] = {'intent': res.intent, 'has_answer': bool(res.answer)}
    intent = res.intent
    chart_req = getattr(res, 'chart_requested', False)
    chart_t = getattr(res, 'chart_type', None)
    out_state = {'intent': intent, 'chart_requested': chart_req, 'chart_type': chart_t, 'events': [node_event('classify', input={'rewritten_text': rewritten.text, 'rewritten': rewritten.model_dump()}, output={'intent': intent, 'reason': res.reason, 'answer': res.answer, 'chart_requested': chart_req, 'chart_type': chart_t}, meta={'llm_used': llm_used, 'user_id': user_id, 'session_id': session_id, 'chart_requested': chart_req, 'chart_type': chart_t})]}
    if res.answer:
        out_state['answer'] = res.answer
    else:
        out_state['answer'] = ''
    return out_state

def _capability_probe_text(state: AgentState) -> str:
    """Ưu tiên câu gốc — rewrite hay ghi đè question thành SQL-like."""
    original = (state['original_question'] if 'original_question' in state else None) or ''
    q = (state['question'] if 'question' in state else None) or ''
    rewritten = state['rewritten'] if 'rewritten' in state else None
    rw = rewritten.text if rewritten is not None and getattr(rewritten, 'text', None) else ''
    return f'{original}\n{q}\n{rw}'


def respond_inline_node(state: AgentState) -> dict:
    from src.domain.agents.nodes.inline_respond import generate_inline_response
    from src.domain.authz.domain_guard import (
        DENY_REPLY,
        format_access_capability_reply,
        is_access_capability_question,
        question_domains_allowed,
    )
    q = state['question'] if 'question' in state else ''
    rewritten = state['rewritten'] if 'rewritten' in state else None
    q_text = rewritten.text if rewritten else q
    ans = ((state['answer'] if 'answer' in state else None) or '').strip()
    intent = state['intent'] if 'intent' in state else 'chat'
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    memories = (state['recalled_memories'] if 'recalled_memories' in state else None) or []
    access = state['access_context'] if 'access_context' in state else None
    probe = _capability_probe_text(state)
    is_capability = is_access_capability_question(probe)
    domain_ok, forbidden = question_domains_allowed(probe, access)
    q_low = q_text.lower()
    is_identity = any((k in q_low for k in ('tôi là ai', 'tên tôi', 'tôi tên', 'biết gì về tôi', 'vai trò của tôi', 'tôi phụ trách gì')))
    with trace_step(current_span(), 'inline_response', input={'intent': intent}, as_type='tool') as sub:
        if is_capability:
            ans = format_access_capability_reply(access)
            intent = 'chat'
        elif not domain_ok:
            # Keyword domain cấm — deny trước greeting out_of_scope
            ans = DENY_REPLY
            intent = 'out_of_scope'
        elif is_identity and memories:
            ans = generate_inline_response(q_text, intent=intent, memories=memories)
        elif intent in ('chat', 'out_of_scope'):
            if not ans:
                ans = generate_inline_response(q_text, intent=intent, memories=memories)
        elif intent == 'clarify' and (not ans):
            ans = 'Bạn có thể nói rõ hơn yêu cầu của mình được không?'
        sub['output'] = {
            'answer_len': len(ans or ''),
            'capability': is_capability,
            'domain_denied': (not domain_ok),
            'forbidden_domains': sorted(forbidden) if forbidden else [],
        }
    resp_mode = 'out_of_scope' if intent == 'out_of_scope' else 'inline'
    return {'answer': ans, 'respond_mode': resp_mode, 'events': [node_event('respond_inline', input={'question': q, 'intent': intent}, output={'answer': ans, 'respond_mode': resp_mode}, meta={'user_id': user_id, 'session_id': session_id, 'capability': is_capability, 'domain_denied': (not domain_ok)})]}

def route_intent(state: AgentState) -> str:
    intent = state['intent'] if 'intent' in state else 'query_data'
    if intent in ('how_to', 'troubleshoot', 'concept'):
        return 'docs'
    elif intent == 'out_of_scope':
        return 'out'
    return 'query_data'

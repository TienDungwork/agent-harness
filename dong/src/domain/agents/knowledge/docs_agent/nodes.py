"""Docs RAG LangGraph nodes."""
from __future__ import annotations
from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState
from src.infra.monitoring.tracing import current_span, trace_step

def retrieve_docs_node(state: AgentState) -> dict:
    from src.domain.knowledge import retrieve_docs
    q = state['question'] if 'question' in state else ''
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    with trace_step(current_span(), 'retrieve_docs', input={'question': q}, as_type='tool') as sub:
        cards = retrieve_docs(q)
        sub['output'] = {'card_count': len(cards)}
    card_ids = [str(c['id'] if 'id' in c else None) for c in cards if isinstance(c, dict) and (c['id'] if 'id' in c else None)]
    titles = [str(c['title'] if 'title' in c else None) for c in cards if isinstance(c, dict) and (c['title'] if 'title' in c else None)]
    return {'events': [node_event('retrieve_docs', input={'question': q}, output={'cards': cards, 'card_count': len(cards), 'card_ids': card_ids, 'titles': titles}, meta={'user_id': user_id, 'session_id': session_id})], 'rows': cards}

def answer_from_docs_node(state: AgentState) -> dict:
    from src.domain.knowledge import answer_from_docs
    from src.infra.memory.context import compress_tool_result
    q = state['question'] if 'question' in state else ''
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    cards = state['rows'] if 'rows' in state else []
    card_ids = [str(c['id'] if 'id' in c else None) for c in cards if isinstance(c, dict) and (c['id'] if 'id' in c else None)]
    docs_ans = answer_from_docs(q, cards)
    dumped = docs_ans.model_dump()
    ans = docs_ans.answer_vi
    if len(ans) > 300 * 4:
        with trace_step(current_span(), 'compress_docs', input={'answer_len': len(ans)}, as_type='tool') as sub:
            ans = compress_tool_result(ans, query=q, max_tokens=300)
            dumped['answer_vi'] = ans
            sub['output'] = {'answer_len': len(ans)}
    return {'answer': ans, 'respond_mode': 'docs', 'docs_answer': dumped, 'events': [node_event('answer_from_docs', input={'question': q, 'cards': cards, 'card_ids': card_ids}, output={'docs_answer': dumped, 'respond_mode': 'docs'}, meta={'user_id': user_id, 'session_id': session_id})]}

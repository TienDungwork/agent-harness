"""Schema retrieval node for SQL path."""
from __future__ import annotations
from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState
from src.infra.db.catalog import build_schema_excerpt, select_relevant_tables
from src.infra.monitoring.tracing import current_span, trace_step

def retrieve_schema_node(state: AgentState) -> dict:
    from src.domain.agents.analytics.sql_agent.tools.batch import query_text_for_state
    q = state['question'] if 'question' in state else ''
    intent = state['intent'] if 'intent' in state else 'query_data'
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    q_text = query_text_for_state(state)
    with trace_step(current_span(), 'select_tables', input={'question': q_text}, as_type='tool'):
        tables = select_relevant_tables(q_text, limit=4)
    from src.domain.authz.domain_guard import DENY_REPLY, filter_tables_by_access
    access = state['access_context'] if 'access_context' in state else None
    tables = filter_tables_by_access(tables, access)
    if not tables and access is not None and not access.allows_all_domains():
        return {'schema_excerpt': '', 'selected_tables': [], 'answer': DENY_REPLY, 'respond_mode': 'out_of_scope', 'error': 'domain_denied', 'events': [node_event('retrieve_schema', input={'intent': intent, 'question': q}, output={'selected_tables': [], 'denied': True}, meta={'user_id': user_id, 'session_id': session_id})]}
    with trace_step(current_span(), 'build_schema_excerpt', input={'tables': tables}, as_type='tool') as sub:
        excerpt = build_schema_excerpt(tables)
        sub['output'] = {'selected_tables': tables, 'schema_length': len(excerpt)}
    return {'schema_excerpt': excerpt, 'selected_tables': tables, 'events': [node_event('retrieve_schema', input={'intent': intent, 'question': q}, output={'schema_excerpt': excerpt, 'selected_tables': tables}, meta={'user_id': user_id, 'session_id': session_id, 'schema_length': len(excerpt), 'selected_tables': tables})]}

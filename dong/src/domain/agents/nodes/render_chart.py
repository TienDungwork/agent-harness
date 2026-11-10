"""Chart render LangGraph node."""
from __future__ import annotations
from typing import Any
from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState
from src.infra.chart.render import _detect_chart_type, plan_chart
from src.infra.monitoring.tracing import current_span, trace_step

def _pad_direction_rows(rows: list, columns: list) -> list:
    """Bổ sung IN/OUT count=0 khi GROUP BY direction chỉ trả một phía."""
    dir_col = next((c for c in columns if str(c).lower() == 'direction'), None)
    if not dir_col:
        return rows
    count_col = next((c for c in columns if str(c).lower() in ('count', 'so_luot', 'total')), columns[-1] if columns else None)
    if not count_col:
        return rows
    present = {str(r[dir_col] if dir_col in r else '').upper() for r in rows if isinstance(r, dict)}
    out = list(rows)
    for d in ('IN', 'OUT'):
        if d not in present:
            out.append({dir_col: d, count_col: 0})
    return out

def render_chart_node(state: AgentState) -> dict:
    """Vẽ chart; thiếu dòng → pad direction / fallback SQL; vẫn thiếu → bỏ chart, không crash graph."""
    rows = list((state['rows'] if 'rows' in state else None) or [])
    columns = list((state['columns'] if 'columns' in state else None) or [])
    sql = (state['sql'] if 'sql' in state else None) or ''
    q = state['question'] if 'question' in state else ''
    user_id = (state['user_id'] if 'user_id' in state else None) or 'default'
    session_id = (state['session_id'] if 'session_id' in state else None) or 'default'
    fallback_applied = False
    if len(rows) < 2:
        rows = _pad_direction_rows(rows, columns)
    if len(rows) < 2:
        from src.domain.agents.analytics.chart_fallback import fallback_chart_query
        fb = fallback_chart_query(question=q, sql=sql, rows=rows)
        if fb:
            rows = list((fb['rows'] if 'rows' in fb else None) or [])
            columns = list((fb['columns'] if 'columns' in fb else None) or columns)
            sql = (fb['sql'] if 'sql' in fb else None) or sql
            fallback_applied = bool(fb['fallback'] if 'fallback' in fb else None)
    if len(rows) < 2:
        return {'rows': rows, 'columns': columns, 'chart_png_base64': '', 'events': [node_event('render_chart', input={'question': q, 'columns': columns, 'rows': rows, 'row_count': len(rows)}, output={'skipped': True, 'reason': 'insufficient_rows', 'row_count': len(rows)}, meta={'user_id': user_id, 'session_id': session_id})]}
    try:
        chart_type = (state['chart_type'] if 'chart_type' in state else None) or _detect_chart_type(q)
        spec = plan_chart(rows, q, chart_type=chart_type)
        with trace_step(current_span(), 'render_png', input={'chart_type': getattr(spec, 'chart_type', '')}, as_type='tool') as sub:
            import src.domain.agents.graph as graph_mod
            png_base64 = graph_mod.render_chart(rows, spec)
            sub['output'] = {'rendered': bool(png_base64), 'png_len': len(png_base64 or '')}
        meta = spec.model_dump() if spec else {}
        ok = bool(png_base64)
        chart_url = ''
        png_for_sse = png_base64 or ''
        if png_base64:
            try:
                import base64
                import logging
                from src.infra.storage.minio_charts import upload_chart_png
                chart_url = upload_chart_png(base64.b64decode(png_base64), session_id=session_id)
                png_for_sse = ''
            except Exception as upload_exc:
                logging.getLogger(__name__).warning('MinIO chart upload failed: %s', upload_exc)
                chart_url = ''
                png_for_sse = png_base64
        node_meta = dict(meta)
        node_meta.update({'user_id': user_id, 'session_id': session_id, 'chart_spec': meta})
        if chart_url:
            node_meta['chart_url'] = chart_url
        out_payload = {'chart_spec': meta, 'rendered': ok, 'chart_png_base64_len': len(png_base64 or ''), 'chart_url': chart_url, 'uploaded': bool(chart_url)}
        if fallback_applied:
            out_payload['fallback_applied'] = True
        return {'rows': rows, 'columns': columns, 'sql': sql, 'chart_png_base64': png_for_sse, 'chart_url': chart_url, 'chart_spec': spec, 'events': [node_event('render_chart', input={'question': q, 'columns': columns, 'rows': rows, 'row_count': len(rows)}, output=out_payload, chart_png_base64=png_for_sse, chart_url=chart_url, chart_meta=meta, chart_spec=meta, meta=node_meta)]}
    except Exception as e:
        raise RuntimeError(f'render_chart failed: {e}') from e

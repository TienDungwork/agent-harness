"""KCN-style VMS analytics agent: slim LLM + one count tool + forced tool_choice.

Same security model as Canvas (no free SQL) — tool wraps ClickHouse gateway helpers.
Uses OpenAI-compatible HTTP (Ollama / LiteLLM) via httpx — no openai package.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from config import Settings

from infra.analytics import daily, daily_multi, require_days_list, summary

_WEEKDAYS_VI = [
    'Thứ Hai',
    'Thứ Ba',
    'Thứ Tư',
    'Thứ Năm',
    'Thứ Sáu',
    'Thứ Bảy',
    'Chủ Nhật',
]

_DATA_INTENT = re.compile(
    r'bao nhieu|thong ke|\btong\b|\bdem\b|\bluot\b|\bxe\b|o to|oto|bien so|'
    r'vehicle|count|plate|hom nay|hom qua|thang|ngay',
    re.I,
)

_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'count_vehicles',
            'description': (
                'Đếm lượt biển số (PLATE) từ ClickHouse. '
                'Ngày Việt Nam DD/MM. Truyền ISO YYYY-MM-DD. '
                'Nhiều ngày: days_list="2026-09-05,2026-09-06". '
                'Hôm nay: days=1. Đọc reply_vi rồi trả lời đúng nội dung đó.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'day': {
                        'type': 'string',
                        'description': 'Một ngày YYYY-MM-DD',
                    },
                    'days_list': {
                        'type': 'string',
                        'description': 'Nhiều ngày CSV YYYY-MM-DD,YYYY-MM-DD',
                    },
                    'days': {
                        'type': 'integer',
                        'description': 'Cửa sổ rolling; 1 = hôm nay',
                    },
                },
            },
        },
    }
]

_SYSTEM = """Bạn là trợ lý phân tích VMS (biển số / lưu lượng xe) trên Agent Canvas.
Giống chatbot KCN: số liệu CHỈ từ tool `count_vehicles`, không bịa.

QUY TẮC:
- LUÔN trả lời tiếng Việt ngắn. Không English.
- Ngày tháng = DD/MM/YYYY (Việt Nam). CẤM MM/DD Mỹ.
  · "tháng 9 năm 2026" + "ngày 5 và ngày 6" → days_list="2026-09-05,2026-09-06"
  · "05/09/2026" → day="2026-09-05"
- Câu đếm xe/biển → BẮT BUỘC gọi count_vehicles trước khi nêu số.
- Nhiều mốc trong một câu → MỘT lần gọi với days_list (đừng quên mốc).
- JSON có reply_vi → trả lời ĐÚNG nội dung đó (copy). Không paraphrase.
- Không nhắc SQL/ClickHouse/tool trong lời văn.
"""


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize('NFD', s or '')
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('đ', 'd').replace('Đ', 'D')


def _force_tool(question: str) -> bool:
    return bool(_DATA_INTENT.search(_strip_accents(question).strip().lower()))


def _now_line() -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    return (
        f'Thời điểm hiện tại: {_WEEKDAYS_VI[now.weekday()]}, {now:%d/%m/%Y %H:%M} '
        f'(giờ Việt Nam, UTC+7). "Hôm nay" theo mốc này.'
    )


def _normalize_model(model: str) -> str:
    m = (model or '').strip()
    if m.startswith('openai/'):
        m = m[len('openai/') :]
    return m or 'qwen3-16k-nothink:latest'


def _llm_conf(settings: Settings) -> tuple[str, str, str]:
    base = (settings.analytics_llm_base_url or '').rstrip('/')
    model = _normalize_model(settings.analytics_llm_model)
    key = settings.analytics_llm_api_key or 'ollama'
    if not base:
        raise RuntimeError('ANALYTICS_LLM_BASE_URL is not configured')
    return base, model, key


def _chat(
    settings: Settings,
    *,
    messages: list[dict[str, Any]],
    tool_choice: str | dict[str, Any] = 'auto',
    stream: bool = False,
) -> Any:
    base, model, key = _llm_conf(settings)
    body: dict[str, Any] = {
        'model': model,
        'messages': messages,
        'tools': _TOOLS,
        'tool_choice': tool_choice,
        'temperature': 0.2,
        'stream': stream,
    }
    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }
    url = f'{base}/chat/completions'
    if stream:
        return httpx.stream('POST', url, headers=headers, json=body, timeout=120.0)
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()


def _run_count_tool(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    days_list = (args.get('days_list') or '').strip()
    day = (args.get('day') or '').strip()
    if days_list:
        return daily_multi(
            settings,
            days_list=require_days_list(days_list),
            module='PLATE',
        )
    if day:
        data = daily(settings, days=1, module='PLATE', day=day)
        total = int(data.get('total_n') or 0)
        y, m, d = day.split('-')
        return {
            'ok': True,
            'day': day,
            'total_n': total,
            'items': data.get('items') or [],
            'reply_vi': f'Ngày {d}/{m}/{y} có {total} lượt biển số.',
        }
    window = int(args.get('days') or 1)
    data = summary(settings, days=window, module='PLATE')
    total = int(data.get('total_n') or 0)
    if window <= 1:
        reply = f'Hôm nay có {total} lượt biển số.'
    else:
        reply = f'{window} ngày gần đây có {total} lượt biển số.'
    return {
        'ok': True,
        'days': window,
        'total_n': total,
        'items': data.get('items') or [],
        'reply_vi': reply,
    }


def _dispatch(settings: Settings, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == 'count_vehicles':
        return _run_count_tool(settings, args)
    return {'error': f'unknown tool {name}'}


def _base_messages(
    question: str, history: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    sys_content = _SYSTEM + '\n\n' + _now_line()
    messages: list[dict[str, Any]] = [{'role': 'system', 'content': sys_content}]
    if history:
        for m in history[-12:]:
            role = m.get('role')
            content = m.get('content')
            if role in ('user', 'assistant') and isinstance(content, str):
                messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': question})
    return messages


def stream_vms_agent(
    settings: Settings,
    question: str,
    history: list[dict[str, Any]] | None = None,
    *,
    max_rounds: int = 4,
) -> Iterator[dict[str, Any]]:
    """Yield {\"delta\": text} for the final answer only (kcn-style)."""
    messages = _base_messages(question, history)
    force = _force_tool(question)

    for _ in range(max_rounds):
        used_tool = any(m.get('role') == 'tool' for m in messages)
        tc: str | dict[str, Any] = 'required' if (force and not used_tool) else 'auto'
        data = _chat(settings, messages=messages, tool_choice=tc, stream=False)
        choice = (data.get('choices') or [{}])[0]
        msg = choice.get('message') or {}
        tool_calls = msg.get('tool_calls') or []

        if not tool_calls:
            content = (msg.get('content') or '').strip()
            # Prefer reply_vi from last tool if model wandered to English
            if content:
                yield {'delta': content}
            return

        messages.append(
            {
                'role': 'assistant',
                'content': msg.get('content'),
                'tool_calls': tool_calls,
            }
        )
        for tc_item in tool_calls:
            fn = tc_item.get('function') or {}
            name = fn.get('name') or ''
            try:
                args = json.loads(fn.get('arguments') or '{}')
            except json.JSONDecodeError:
                args = {}
            result = _dispatch(settings, name, args)
            messages.append(
                {
                    'role': 'tool',
                    'tool_call_id': tc_item.get('id'),
                    'content': json.dumps(result, ensure_ascii=False)[:8000],
                }
            )
            # Fast path: if tool already gave reply_vi, emit it and stop
            # (one fewer LLM round — kcn still does a final round; we can skip
            # when reply_vi is authoritative like SSH harness).
            reply = result.get('reply_vi') if isinstance(result, dict) else None
            if isinstance(reply, str) and reply.strip():
                yield {'delta': reply.strip()}
                return

    yield {'delta': 'Xin lỗi, em chưa tổng hợp được câu trả lời.'}

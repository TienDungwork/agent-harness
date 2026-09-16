from __future__ import annotations

import json
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from auth.deps import require_session
from auth.session import SessionManager
from config import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from storage.credits import (
    InsufficientCredits,
    charge_credits,
    raise_http_for_credits,
    refund_credits,
)
from storage.models import User, UserConversation, UserSettingsBlob, get_db
from storage.users import (
    AuthUser,
    claim_conversation,
    list_user_conversation_ids,
    to_auth_user,
)

router = APIRouter(tags=['proxy'])

_BRANDING_JS = Path(__file__).resolve().parent / 'beszel_branding.js'


@lru_cache(maxsize=1)
def _beszel_branding_inject() -> bytes:
    """Inline Creanova branding script (title + logo SVG + All Systems)."""
    script = _BRANDING_JS.read_text(encoding='utf-8')
    return b'<script>' + script.encode('utf-8') + b'</script>'


_CONV_RE = re.compile(
    r'^/api/conversations(?:/(?P<cid>[0-9a-fA-F-]{36}))?(?P<rest>/.*)?$'
)

_PUBLIC_PREFIXES = (
    '/healthz',
    '/api/auth/login',
    '/ready',
    '/alive',
    '/server_info',
    '/docs',
    '/redoc',
    '/openapi.json',
)

# Suffixes on /api/conversations/{id}/... that consume credits (agent work).
_CHARGEABLE_CONV_SUFFIXES = (
    '/events',
    '/ask_agent',
    '/run',
    '/message',
    '/start',
)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PREFIXES:
        return True
    return any(path.startswith(p + '/') for p in ('/docs',))


def _extract_conversation_id(path: str) -> str | None:
    m = _CONV_RE.match(path)
    if not m:
        return None
    return m.group('cid')


def _gateway_blocks_forward(path: str) -> bool:
    """True when the catch-all must 404 instead of forwarding to agent-server.

    Credits/admin/infra are gateway-only. ``/api/auth/*`` is not blocked:
    login/me/logout are on the dedicated auth router, and unmatched routes
    such as ``/api/auth/workspace-session`` belong to agent-server.
    """
    return (
        path.startswith('/api/credits/')
        or path.startswith('/api/admin/')
        or path.startswith('/api/infra/')
    )


def _is_expose_secrets_header(value: str | None) -> bool:
    """True when the client asked for secrets, not the UI-redacted document.

    Agent-server accepts ``encrypted`` / ``plaintext`` / ``true``. The redacted
    GET (no header) is safe to blob-cache; the expose GET is not — it must
    round-trip Fernet LLM keys for conversation start.
    """
    if not value:
        return False
    return value.lower().strip() in {'encrypted', 'plaintext', 'true'}


def _blob_kind_for_path(path: str) -> str | None:
    if path == '/api/settings':
        return 'settings'
    if path == '/api/settings/secrets' or path.startswith('/api/settings/secrets/'):
        return 'secrets'
    # Do not blob-cache /api/profiles. Saves go to /api/profiles/{name} and
    # forward to agent-server, so a cached GET list never picks up creates,
    # renames, deletes, or activate — the UI appears stuck on one profile.
    return None


def _is_usable_settings_blob(payload: Any) -> bool:
    """Reject PATCH request bodies mistakenly stored as the settings document.

    A real settings GET returns ``agent_settings`` / ``conversation_settings``.
    Storing ``{"agent_settings_diff": ...}`` made later GETs look like the
    LLM base_url and API key were wiped after every profile update.
    """
    if not isinstance(payload, dict):
        return False
    if 'agent_settings_diff' in payload and 'agent_settings' not in payload:
        return False
    if 'conversation_settings_diff' in payload and 'agent_settings' not in payload:
        return False
    return 'agent_settings' in payload or 'conversation_settings' in payload


def _is_slow_uv_infra_mcp(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    command = entry.get('command')
    if command in ('uv', 'uvx'):
        return True
    args = entry.get('args')
    if not isinstance(args, list):
        return False
    str_args = [str(a) for a in args]
    return '--with' in str_args and any('mcp' in a for a in str_args)


_INFRA_MCP_ENV = {
    'GATEWAY_URL': 'http://local-gateway:18110',
    'MCP_VMS_ONLY': '1',
}


def _fast_infra_mcp_config(agent: dict) -> None:
    """Replace legacy ``uv run --with mcp`` with system python3 (~2–3s saved)."""
    mcp = agent.get('mcp_config')
    if not isinstance(mcp, dict):
        mcp = {}
        agent['mcp_config'] = mcp

    for name in ('creanova_infra', 'creanova-infra'):
        if name in mcp and _is_slow_uv_infra_mcp(mcp.get(name)):
            del mcp[name]

    has_usable = any(
        name in mcp and not _is_slow_uv_infra_mcp(mcp.get(name))
        for name in ('creanova_infra', 'creanova-infra')
    )
    if has_usable:
        # Existing config may omit MCP_VMS_ONLY — force it so tool schemas stay small.
        for name in ('creanova_infra', 'creanova-infra'):
            cfg = mcp.get(name)
            if isinstance(cfg, dict):
                env = dict(cfg.get('env') or {})
                env.update(_INFRA_MCP_ENV)
                cfg['env'] = env
                mcp[name] = cfg
        return

    mcp['creanova_infra'] = {
        'command': 'python3',
        'args': ['/opt/infra-mcp/mcp_stdio.py'],
        'env': dict(_INFRA_MCP_ENV),
    }


_FERNET_API_KEY_PREFIX = 'gAAAA'
_REDACTED_API_KEYS = frozenset({'**********', '***'})


def _is_fernet_api_key(value: object) -> bool:
    return isinstance(value, str) and value.startswith(_FERNET_API_KEY_PREFIX)


def _is_redacted_api_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    trimmed = value.strip()
    if not trimmed:
        return False
    if trimmed in _REDACTED_API_KEYS:
        return True
    return bool(re.fullmatch(r'\*+', trimmed))


def _is_usable_plaintext_api_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    trimmed = value.strip()
    if not trimmed:
        return False
    if _is_redacted_api_key(trimmed) or _is_fernet_api_key(trimmed):
        return False
    return True


def _sanitize_blob_llm(blob_llm: dict) -> dict:
    """Copy UI blob LLM without redacted/empty api_key sentinels."""
    out = dict(blob_llm)
    key = out.get('api_key')
    if not _is_usable_plaintext_api_key(key) and not _is_fernet_api_key(key):
        out.pop('api_key', None)
    return out


def _is_fast_local_llm_base(base_url: str) -> bool:
    b = (base_url or '').lower()
    if ':11434' in b or 'ollama' in b:
        return True
    # RFC1918 / localhost OpenAI-compatible endpoints.
    for host in (
        '127.0.0.1',
        'localhost',
        '192.168.',
        '10.',
        '172.16.',
        '172.17.',
        '172.18.',
        '172.19.',
        '172.2',
        '172.30.',
        '172.31.',
    ):
        if host in b:
            return True
    return False


def _rewrite_llm_from_ui_blob(agent: dict, settings_blob: object) -> bool:
    """Prefer a fast local LLM (Ollama / LAN) over encrypted disk or tunnels.

    Returns True when ``llm.api_key`` is usable plaintext (safe to set
    ``secrets_encrypted=False``). Fernet keys must keep ``secrets_encrypted=True``
    so the agent-server decrypts them — forcing False caused missing/invalid
    OPENAI_API_KEY AuthenticationError when logging in from another client.
    """
    llm = dict(agent.get('llm') or {})
    blob_llm: dict | None = None
    if isinstance(settings_blob, dict):
        blob_agent = settings_blob.get('agent_settings')
        if isinstance(blob_agent, dict) and isinstance(blob_agent.get('llm'), dict):
            blob_llm = blob_agent.get('llm')  # type: ignore[assignment]

    if isinstance(blob_llm, dict):
        model = blob_llm.get('model')
        base_url = blob_llm.get('base_url')
        if isinstance(model, str) and model.strip():
            llm['model'] = model.strip()
        if isinstance(base_url, str) and base_url.strip():
            llm['base_url'] = base_url.strip()

    base = str(llm.get('base_url') or '')
    if not _is_fast_local_llm_base(base):
        from config import get_settings

        settings = get_settings()
        analytics_base = (settings.analytics_llm_base_url or '').strip()
        analytics_model = (settings.analytics_llm_model or '').strip()
        if analytics_base and _is_fast_local_llm_base(analytics_base):
            llm['base_url'] = analytics_base
            if analytics_model:
                llm['model'] = analytics_model
            llm['api_key'] = (settings.analytics_llm_api_key or '').strip() or 'ollama'
            base = analytics_base

    if _is_fast_local_llm_base(base):
        key = llm.get('api_key')
        if not _is_usable_plaintext_api_key(key):
            blob_key = blob_llm.get('api_key') if isinstance(blob_llm, dict) else None
            if _is_usable_plaintext_api_key(blob_key):
                llm['api_key'] = blob_key
            else:
                llm['api_key'] = 'ollama'
        model = str(llm.get('model') or '').strip()
        if model and '/' not in model:
            llm['model'] = f'openai/{model}'
        agent['llm'] = llm
        return True

    key = llm.get('api_key')
    if _is_usable_plaintext_api_key(key):
        agent['llm'] = llm
        return True
    if _is_fernet_api_key(key):
        agent['llm'] = llm
        return False

    blob_key = blob_llm.get('api_key') if isinstance(blob_llm, dict) else None
    if _is_usable_plaintext_api_key(blob_key):
        llm['api_key'] = blob_key
        agent['llm'] = llm
        return True
    if _is_fernet_api_key(blob_key):
        llm['api_key'] = blob_key
        agent['llm'] = llm
        return False

    if _is_redacted_api_key(key) or key in ('', None):
        llm.pop('api_key', None)
    if llm.get('base_url'):
        llm['api_key'] = 'sk-local'
        agent['llm'] = llm
        return True

    agent['llm'] = llm
    return False


def _lean_conversation_create_body(
    body: bytes, settings_blob: object | None = None
) -> bytes:
    """Strip the ~60 bundled coding skills from conversation create.

    Agent Canvas UI sometimes still injects the public skill catalog (or a
    cached overlay does), which dominates create latency (~10s) and every
    LLM turn (~480KB dynamic context). For this self-hosted VMS stack, force
    a lean agent_context before the agent-server sees it.

    Named ``agent_profile_id`` launches resolve skills server-side via
    ``discover_profile_skills``; that path is neutralized by
    ``patch_no_profile_skills``. Here we still strip any inline agent_settings
    and refuse to trust a client-supplied skills array.
    """
    if not body:
        return body
    try:
        payload = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    # Named profiles re-inject coding tools/skills. Convert to lean
    # agent_settings using the UI blob's LLM (Ollama), not the stale profile.
    if payload.get('agent_profile_id') and isinstance(settings_blob, dict):
        blob_agent = settings_blob.get('agent_settings')
        blob_llm = blob_agent.get('llm') if isinstance(blob_agent, dict) else None
        payload.pop('agent_profile_id', None)
        lean_agent = {
            'agent_kind': 'Creanova',
            'llm': (_sanitize_blob_llm(blob_llm) if isinstance(blob_llm, dict) else {}),
            'mcp_config': (
                blob_agent.get('mcp_config')
                if isinstance(blob_agent, dict)
                and isinstance(blob_agent.get('mcp_config'), dict)
                else {}
            ),
            'agent_context': {},
            'tools': [],
            'include_default_tools': ['FinishTool'],
            'enable_switch_llm_tool': False,
            'condenser': {'condenser_kind': 'no_op'},
        }
        payload['agent_settings'] = lean_agent
        payload['agent'] = lean_agent
        # Create used encrypted secrets from disk; lean agent has plaintext
        # ollama key after rewrite — do not ask the server to decrypt.
        payload['secrets_encrypted'] = False

    agent = payload.get('agent_settings')
    if not isinstance(agent, dict):
        # Some clients nest under ``agent`` instead of ``agent_settings``.
        agent = payload.get('agent')
    if not isinstance(agent, dict):
        return body

    ctx = agent.get('agent_context')
    if not isinstance(ctx, dict):
        ctx = {}
        agent['agent_context'] = ctx
    ctx['skills'] = []
    ctx['load_public_skills'] = False
    ctx['load_user_skills'] = False
    ctx['load_project_skills'] = False
    ctx['disabled_skills'] = []

    # Skip ThinkTool — extra LLM round on simple analytics questions.
    agent['include_default_tools'] = ['FinishTool']
    agent['enable_switch_llm_tool'] = False

    # Coding tools compete with MCP on every turn (~seconds of tool-choice).
    # Analytics via MCP vms_query only (MCP_VMS_ONLY). Keep SDK tools empty.
    agent['tools'] = []

    # Condenser fires a second LLM — use NoOp for lean VMS/SSH turns.
    # OpenHandsAgentSettings discriminator is ``condenser_kind``, not ``kind``.
    agent['condenser'] = {'condenser_kind': 'no_op'}

    # Align LLM with the UI settings blob (local Ollama), not stale LiteLLM disk.
    plaintext_llm_key = _rewrite_llm_from_ui_blob(agent, settings_blob)

    # Local Ollama: string-serialized tool calls + "reasoning" knobs add
    # tens of seconds before the first <function=…> appears.
    llm = agent.get('llm')
    if isinstance(llm, dict):
        llm = {
            **llm,
            'temperature': 0.1,
            'stream': False,
            'force_string_serializer': False,
            'native_tool_calling': True,
            'reasoning_effort': None,
            'reasoning_summary': None,
            'enable_encrypted_reasoning': False,
            'extended_thinking_budget': None,
            'prompt_cache_retention': None,
            # Cap completion — greets/VMS reply_vi are short; long max slows decode.
            'max_output_tokens': 128,
        }
        agent['llm'] = llm
        # Only disable decrypt when we actually installed plaintext.
        # Fernet keys from X-Expose-Secrets: encrypted must stay decryptable.
        if plaintext_llm_key:
            payload['secrets_encrypted'] = False
        elif _is_fernet_api_key(llm.get('api_key')):
            payload['secrets_encrypted'] = True

    # Keep agent/agent_settings in sync when both are present.
    if isinstance(payload.get('agent'), dict):
        payload['agent'] = agent
    payload['agent_settings'] = agent

    # Always keep lean MCP on local creates. Stripping it for greetings broke
    # mid-chat VMS ("số xe…") — conversation had FinishTool only → empty LLM
    # replies + corrective nudge loops (10–15s). Warm-pool hides the ~2s handshake.
    _fast_infra_mcp_config(agent)

    # Default SDK static prompt is ~16KB coding rules (CODE_QUALITY, SECURITY…).
    # That alone adds seconds of Ollama prefill vs a direct API call. Force the
    # short Canvas SOUL (+ harness clock) as an inline system_prompt.
    _apply_lean_system_prompt(agent)

    payload.get('initial_message')

    # Autotitle fires a second LLM call (~5–15s on LAN) before/after the reply.
    payload['autotitle'] = False
    # LLM security analyzer is another extra call — skip for lean VMS/SSH.
    payload['security_analyzer'] = None

    try:
        return json.dumps(payload, ensure_ascii=False).encode('utf-8')
    except (TypeError, ValueError):
        return body


# Keep in sync with agent-canvas/config/SOUL.md (VMS lean identity).
_LEAN_SOUL = """\
<SOUL>
You are Creanova, a local AI assistant on this machine via Agent Canvas.

Language: ALWAYS reply in Vietnamese (tiếng Việt) — kể cả khi user hỏi tiếng Anh. Short answers (1–5 lines). Prefer tools over guessing. Do not invent product docs URLs. Never answer analytics in English.
Do not lecture or explain command output unless the user asks "giải thích/why".
No emoji section headers. No encyclopedias about Docker/veth/K8s/WireGuard.
Do not use the think tool for greetings or simple data questions.

Never invent tool parameters. CẤM `security_risk`, CẤM `summary`. Only listed parameters (e.g. q=, day=).

Do NOT call canvas_ui_control / navigate_to_file for greetings, SSH, analytics, or loops.
Only use canvas_ui_control after a user-requested file edit, once per step.

VMS / ClickHouse (bắt buộc — agent TỰ GỌI tool, không bịa số):
- Ngày = DD/MM/YYYY (VN). CẤM MM/DD Mỹ.
  · "tháng M" + "ngày D1 và D2" → days_list="YYYY-MM-D1,YYYY-MM-D2"
  · "DD/MM/YYYY" → day="YYYY-MM-DD". Hôm nay → bỏ day hoặc days=1.
- Chỉ 1 tool: `vms_query(action=…)`. action = count | flow | manufacturer | trace | intrusion.
- Đếm ô tô/xe máy: count + vehicle_type=CAR|MOTORCYCLE|TRUCK (CẤM MOTORBIKE).
- Có `reply_vi` → copy nguyên rồi FinishTool. Cấm English / paraphrase / gọi thêm tool.
- CẤM viết `<tool_call>` trong text — dùng native function call.
- CLOCK = ngày thật.
</SOUL>"""


def _vietnam_now_line() -> str:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone(timedelta(hours=7)))
    weekdays = (
        'Thứ Hai',
        'Thứ Ba',
        'Thứ Tư',
        'Thứ Năm',
        'Thứ Sáu',
        'Thứ Bảy',
        'Chủ Nhật',
    )
    # datetime.weekday(): Mon=0 … Sun=6
    wd = weekdays[now.weekday()]
    return (
        f'Thời điểm hiện tại: {wd}, {now.strftime("%d/%m/%Y %H:%M")} '
        f'(giờ Việt Nam, UTC+7). "Hôm nay" theo mốc này — không bịa năm 2018.'
    )


def _lean_harness_suffix() -> str:
    return (
        '<LOCAL_HARNESS>\n'
        'Creanova Agent Canvas (self-hosted). Follow this over Cloud defaults.\n\n'
        f'CLOCK: {_vietnam_now_line()}\n\n'
        'Rules\n'
        '- ALWAYS tiếng Việt. Short. No English analytics.\n'
        '- CẤM invent params: no security_risk, no summary.\n'
        '- Data → call vms_query first → if JSON has reply_vi, copy it and '
        'FinishTool. Do not retype slowly / paraphrase.\n'
        '- vms_query action=: count | flow | manufacturer | trace | intrusion\n'
        '- Dates DD/MM (VN). "tháng 9"+"ngày 5 và 6" → '
        'days_list=2026-09-05,2026-09-06\n'
        '</LOCAL_HARNESS>'
    )


def _apply_lean_system_prompt(agent: dict) -> None:
    """Replace the ~16KB SDK coding prompt with Canvas SOUL + LOCAL_HARNESS."""
    existing = agent.get('system_prompt')
    if not (isinstance(existing, str) and existing.strip()):
        agent['system_prompt'] = _LEAN_SOUL
    ctx = agent.get('agent_context')
    if not isinstance(ctx, dict):
        ctx = {}
        agent['agent_context'] = ctx
    suffix = ctx.get('system_message_suffix')
    if not (isinstance(suffix, str) and '<LOCAL_HARNESS>' in suffix):
        ctx['system_message_suffix'] = _lean_harness_suffix()


_PLATE_TOKEN_RE = re.compile(
    r'(?<![A-Z0-9])(\d{1,3}[A-Z]{1,3}-?\d{3,6})(?![A-Z0-9])',
    re.I,
)
_TRACE_HINT_RE = re.compile(
    r'truy\s*v[ếe]t|l[ịi]ch\s*s[ửu]|bi[ểe]n\s*s[ốo]',
    re.I,
)
_COUNT_HINT_RE = re.compile(
    r'([đd][ếe]m|bao\s*nhi[êe]u|s[ốo]\s*(?:lư[ợo]ng\s*)?xe|lư[ợo]t\s*bi[ểe]n|'
    r'ra\s*v[àa]o|h[ãa]ng\s*xe|x[âa]m\s*nh[ậa]p|xe\s*m[áa]y|'
    r'g[ầa]n\s*nh[ấa]t|ngày\s*g[ầa]n)',
    re.I,
)
_SSH_HINT_RE = re.compile(
    r'\bssh\b|infra_|server|máy\s*ch[ủu]|container|docker|uptime|disk|cpu',
    re.I,
)


def _initial_message_text(initial: object) -> str:
    if not isinstance(initial, dict):
        return ''
    content = initial.get('content')
    text = ''
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get('type') == 'text':
                text += str(part.get('text') or '')
    elif isinstance(content, str):
        text = content
    return text.strip()


def _needs_infra_mcp(initial: object) -> bool:
    text = _initial_message_text(initial)
    if not text:
        return False
    if _PLATE_TOKEN_RE.search(text):
        return True
    if _TRACE_HINT_RE.search(text) or _COUNT_HINT_RE.search(text):
        return True
    if _SSH_HINT_RE.search(text):
        return True
    return False


def _lean_events_body(body: bytes) -> bytes:
    """Passthrough for mid-chat events (no forced tool hints — agent chooses)."""
    return body


def _is_chargeable_conversation_post(
    path: str,
) -> tuple[bool, str | None, float | None]:
    """Return (chargeable, conversation_id, cost_key).

    cost_key is 'conversation' or 'run'.
    """
    if path.rstrip('/') == '/api/conversations':
        return True, None, 'conversation'
    m = _CONV_RE.match(path)
    if not m:
        return False, None, None
    cid = m.group('cid')
    rest = m.group('rest') or ''
    for suffix in _CHARGEABLE_CONV_SUFFIXES:
        if rest == suffix or rest.startswith(suffix + '/'):
            return True, cid, 'run'
    return False, cid, None


def _get_blob(db: Session, user_id: str, kind: str) -> Any | None:
    row = (
        db.query(UserSettingsBlob)
        .filter(UserSettingsBlob.user_id == user_id, UserSettingsBlob.kind == kind)
        .one_or_none()
    )
    if row is None:
        return None
    payload = row.payload
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return {}


def _put_blob(db: Session, user_id: str, kind: str, payload: Any) -> Any:
    row = (
        db.query(UserSettingsBlob)
        .filter(UserSettingsBlob.user_id == user_id, UserSettingsBlob.kind == kind)
        .one_or_none()
    )
    if row is None:
        row = UserSettingsBlob(user_id=user_id, kind=kind, payload=payload)
        db.add(row)
    else:
        row.payload = payload
    db.commit()
    return payload


def _delete_blob(db: Session, user_id: str, kind: str) -> None:
    row = (
        db.query(UserSettingsBlob)
        .filter(UserSettingsBlob.user_id == user_id, UserSettingsBlob.kind == kind)
        .one_or_none()
    )
    if row is not None:
        db.delete(row)
        db.commit()


async def _forward(
    request: Request,
    settings: Settings,
    *,
    path: str | None = None,
    body: bytes | None = None,
) -> Response:
    target_path = path or request.url.path
    url = f'{settings.agent_server_url.rstrip("/")}{target_path}'
    if request.url.query:
        url = f'{url}?{request.url.query}'

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {
            'host',
            'content-length',
            'connection',
            'cookie',
            'transfer-encoding',
        }
    }
    if settings.agent_server_api_key:
        headers['X-Session-API-Key'] = settings.agent_server_api_key

    if body is None and request.method not in ('GET', 'HEAD'):
        body = await request.body()

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )

    excluded = {'content-encoding', 'transfer-encoding', 'content-length', 'connection'}
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get('content-type'),
    )


def _filter_conversation_page(payload: Any, allowed: set[str]) -> Any:
    if not isinstance(payload, dict):
        return payload
    items = payload.get('items')
    if isinstance(items, list):
        filtered = []
        for item in items:
            cid = None
            if isinstance(item, dict):
                cid = item.get('id') or item.get('conversation_id')
            if cid is None or str(cid) in allowed:
                filtered.append(item)
        payload = {**payload, 'items': filtered}
    return payload


@router.api_route(
    '/beszel/{full_path:path}',
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
)
async def proxy_beszel(
    full_path: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    """Reverse-proxy Beszel hub. Requires GW session. Strips X-Frame-Options."""
    require_session(request, settings, SessionManager(settings))

    target = f'{settings.beszel_hub_url.rstrip("/")}/{full_path}'
    if request.url.query:
        target = f'{target}?{request.url.query}'

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {'host', 'content-length', 'connection', 'transfer-encoding'}
    }

    body = None
    if request.method not in ('GET', 'HEAD'):
        body = await request.body()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        upstream = await client.request(
            request.method, target, headers=headers, content=body
        )

    excluded = {
        'content-encoding',
        'transfer-encoding',
        'content-length',
        'connection',
        'x-frame-options',
        'content-security-policy',
    }
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    content: bytes = upstream.content
    media = upstream.headers.get('content-type') or ''
    if 'text/html' in media and b'</body>' in content and b'BESZEL' in content:
        content = content.replace(
            b'<title>Beszel</title>', b'<title>Creanova</title>', 1
        )
        boot = (
            b'<style id="creanova-boot">'
            b'a[aria-label="Home"]>svg:not(#creanova-logo)'
            b'{visibility:hidden!important;position:absolute!important;'
            b'width:0!important;height:0!important;overflow:hidden!important}'
            b'a[aria-label="Home"]{margin-inline-end:.15rem!important;'
            b'padding-block:.25rem!important;padding-inline:0!important}'
            b'</style>'
        )
        if b'id="creanova-boot"' not in content and b'</head>' in content:
            content = content.replace(b'</head>', boot + b'</head>', 1)
        try:
            inject = _beszel_branding_inject()
        except OSError:
            inject = b''
        if inject:
            # Prefer </head> so MutationObserver is ready before React paints.
            if b'</head>' in content:
                content = content.replace(b'</head>', inject + b'</head>', 1)
            else:
                content = content.replace(b'</body>', inject + b'</body>', 1)

    return Response(
        content=content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get('content-type'),
    )


@router.api_route(
    '/api/{full_path:path}',
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
)
async def proxy_api(
    full_path: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    path = f'/api/{full_path}'

    if _gateway_blocks_forward(path):
        raise HTTPException(status_code=404, detail='Not found')

    user: AuthUser | None = None
    if not _is_public(path):
        try:
            session = require_session(request, settings, SessionManager(settings))
        except HTTPException:
            raise
        row = db.query(User).filter(User.id == session.user_id).one_or_none()
        if row is None or not row.is_active:
            raise HTTPException(status_code=401, detail='User not found or disabled')
        user = to_auth_user(row)

    assert user is not None or _is_public(path)

    # Per-user opaque blobs for settings / secrets (profiles always forward).
    blob_kind = _blob_kind_for_path(path) if user is not None else None
    if blob_kind and user is not None:
        # Only intercept collection-level reads/writes for secrets;
        # nested paths still forward but we keep ownership via cookie gate.
        collection_only = path in (
            '/api/settings',
            '/api/settings/secrets',
        )
        if collection_only and request.method == 'GET':
            # Never serve/cache the redacted settings blob for expose-secrets
            # GETs. Conversation start sends X-Expose-Secrets: encrypted; a
            # cached UI document has api_key "**********" which the SDK
            # turns into None → LLMAuthenticationError.
            if blob_kind == 'settings' and _is_expose_secrets_header(
                request.headers.get('X-Expose-Secrets')
            ):
                return await _forward(request, settings)
            blob = _get_blob(db, user.id, blob_kind)
            if blob is not None and (
                blob_kind != 'settings' or _is_usable_settings_blob(blob)
            ):
                return Response(
                    content=json.dumps(blob),
                    media_type='application/json',
                    status_code=200,
                )
            resp = await _forward(request, settings)
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.body)
                    if blob_kind != 'settings' or _is_usable_settings_blob(data):
                        _put_blob(db, user.id, blob_kind, data)
                except Exception:
                    pass
            return resp
        if collection_only and request.method in ('PUT', 'POST', 'PATCH'):
            body = await request.body()
            try:
                json.loads(body.decode('utf-8') or '{}')
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail='Invalid JSON') from exc
            # Store the upstream *response* (full document), never the PATCH
            # request body — otherwise GET /api/settings serves diffs and the
            # UI thinks base_url / api_key were cleared.
            resp = await _forward(request, settings, body=body)
            if 200 <= resp.status_code < 300:
                if blob_kind == 'settings':
                    try:
                        data = json.loads(resp.body)
                        if _is_usable_settings_blob(data):
                            _put_blob(db, user.id, blob_kind, data)
                    except Exception:
                        pass
                else:
                    # Secrets mutations: drop cache so the next GET refreshes.
                    _delete_blob(db, user.id, blob_kind)
            return resp

    # Conversation ownership + credits
    if user is not None and path.startswith('/api/conversations'):
        cid = _extract_conversation_id(path)
        allowed = list_user_conversation_ids(db, user.id)

        if cid and request.method != 'POST':
            if cid not in allowed:
                row = (
                    db.query(UserConversation)
                    .filter(UserConversation.conversation_id == cid)
                    .one_or_none()
                )
                if row is None:
                    try:
                        claim_conversation(db, user.id, cid)
                        allowed.add(cid)
                    except PermissionError as exc:
                        raise HTTPException(status_code=403, detail=str(exc)) from exc
                elif row.user_id != user.id:
                    raise HTTPException(
                        status_code=403, detail='Conversation forbidden'
                    )

        if request.method == 'POST':
            chargeable, charge_cid, cost_key = _is_chargeable_conversation_post(path)
            reserved_run_id: str | None = None
            reserved_cost = 0.0

            if chargeable and cost_key:
                reserved_cost = (
                    settings.credit_cost_per_conversation
                    if cost_key == 'conversation'
                    else settings.credit_cost_per_run
                )
                reserved_run_id = (
                    f'create:{uuid.uuid4()}'
                    if cost_key == 'conversation'
                    else f'run:{charge_cid}:{uuid.uuid4()}'
                )
                try:
                    charge_credits(
                        db,
                        user_id=user.id,
                        cost=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                        usage_type=(
                            'conversation_create'
                            if cost_key == 'conversation'
                            else 'llm_run'
                        ),
                    )
                except InsufficientCredits as exc:
                    raise_http_for_credits(exc)

            if path.rstrip('/') == '/api/conversations':
                body = await request.body()
                settings_blob = _get_blob(db, user.id, 'settings')
                body = _lean_conversation_create_body(body, settings_blob)
                resp = await _forward(request, settings, body=body)
                if 200 <= resp.status_code < 300:
                    try:
                        data = json.loads(resp.body)
                        new_id = data.get('id') or data.get('conversation_id')
                        if new_id:
                            from storage.conversations import (
                                touch_conversation,
                                upsert_conversation_tool,
                            )

                            title = data.get('title')
                            touch_conversation(
                                db,
                                conversation_id=str(new_id),
                                user_id=user.id,
                                title=title if isinstance(title, str) else None,
                                llm_model=(
                                    data.get('model')
                                    if isinstance(data.get('model'), str)
                                    else None
                                ),
                            )
                            # Record tools hinted in create response / agent config.
                            tools = data.get('tools') or data.get('enabled_tools') or []
                            if isinstance(tools, list):
                                for t in tools:
                                    if isinstance(t, str):
                                        upsert_conversation_tool(
                                            db,
                                            conversation_id=str(new_id),
                                            user_id=user.id,
                                            tool_kind='builtin',
                                            tool_name=t,
                                        )
                                    elif isinstance(t, dict) and t.get('name'):
                                        upsert_conversation_tool(
                                            db,
                                            conversation_id=str(new_id),
                                            user_id=user.id,
                                            tool_kind=str(t.get('kind') or 'builtin'),
                                            tool_name=str(t['name']),
                                            tool_version=(
                                                str(t['version'])
                                                if t.get('version')
                                                else None
                                            ),
                                        )
                    except Exception:
                        pass
                elif reserved_cost > 0 and reserved_run_id:
                    refund_credits(
                        db,
                        user_id=user.id,
                        amount=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                    )
                return resp

            if chargeable and cost_key == 'run':
                body = await request.body()
                if path.rstrip('/').endswith('/events') or '/events' in path:
                    body = _lean_events_body(body)
                resp = await _forward(request, settings, body=body)
                if (
                    not (200 <= resp.status_code < 300)
                    and reserved_cost > 0
                    and reserved_run_id
                ):
                    refund_credits(
                        db,
                        user_id=user.id,
                        amount=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                    )
                return resp

        if (
            path.rstrip('/')
            in (
                '/api/conversations/search',
                '/api/conversations',
            )
            and request.method == 'GET'
        ):
            resp = await _forward(request, settings)
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.body)
                    filtered = _filter_conversation_page(data, allowed)
                    return Response(
                        content=json.dumps(filtered),
                        status_code=200,
                        media_type='application/json',
                    )
                except Exception:
                    return resp
            return resp

        if path.endswith('/batch') and request.method == 'POST':
            body = await request.body()
            try:
                payload = json.loads(body.decode('utf-8') or '[]')
            except json.JSONDecodeError:
                payload = []
            if isinstance(payload, list):
                payload = [x for x in payload if str(x) in allowed]
                body = json.dumps(payload).encode('utf-8')
            return await _forward(request, settings, body=body)

    # Activate rewrites agent-server settings; invalidate the per-user settings
    # blob so the next GET does not keep showing the previous model/base_url.
    if (
        user is not None
        and request.method == 'POST'
        and path.endswith('/activate')
        and (
            path.startswith('/api/profiles/') or path.startswith('/api/agent-profiles/')
        )
    ):
        resp = await _forward(request, settings)
        if 200 <= resp.status_code < 300:
            _delete_blob(db, user.id, 'settings')
        return resp

    return await _forward(request, settings)

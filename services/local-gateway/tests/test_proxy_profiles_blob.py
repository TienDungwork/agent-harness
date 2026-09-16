"""Regression: LLM profile list must not be served from a stale per-user blob.

Creates/updates go to ``/api/profiles/{name}`` and forward to agent-server, but
the gateway used to cache ``GET /api/profiles`` in ``user_settings_blobs``.
After a successful create the UI still saw the old list.
"""

from __future__ import annotations

from proxy import (
    _blob_kind_for_path,
    _gateway_blocks_forward,
    _is_expose_secrets_header,
    _is_usable_settings_blob,
)


def test_profiles_paths_are_not_blob_cached():
    """Profiles must always forward; list mutations never refresh the blob."""
    assert _blob_kind_for_path('/api/profiles') is None
    assert _blob_kind_for_path('/api/profiles/nemotron') is None
    assert _blob_kind_for_path('/api/profiles/nemotron/activate') is None


def test_settings_and_secrets_still_use_blobs():
    assert _blob_kind_for_path('/api/settings') == 'settings'
    assert _blob_kind_for_path('/api/settings/secrets') == 'secrets'
    assert _blob_kind_for_path('/api/settings/secrets/FOO') == 'secrets'


def test_workspace_session_forwards_to_agent_server():
    """Agent-server mints the workspace cookie; gateway must not 404 it."""
    assert _gateway_blocks_forward('/api/auth/workspace-session') is False
    assert _gateway_blocks_forward('/api/credits/balance') is True
    assert _gateway_blocks_forward('/api/admin/users') is True
    assert _gateway_blocks_forward('/api/infra/servers') is True


def test_encrypted_settings_get_is_not_blob_cached():
    """GET /api/settings with X-Expose-Secrets must not reuse the redacted blob.

    Conversation start sends ``X-Expose-Secrets: encrypted`` so Fernet LLM keys
    round-trip. The UI GET (no header) caches ``api_key: **********``. Serving
    that blob to the encrypted GET starts chats with no key (LLMAuthenticationError).
    """
    assert _is_expose_secrets_header(None) is False
    assert _is_expose_secrets_header('') is False
    assert _is_expose_secrets_header('encrypted') is True
    assert _is_expose_secrets_header('ENCRYPTED') is True
    assert _is_expose_secrets_header('plaintext') is True
    assert _is_expose_secrets_header('true') is True
    assert _is_expose_secrets_header('false') is False


def test_settings_patch_diff_is_not_a_usable_blob():
    assert _is_usable_settings_blob({'agent_settings_diff': {}}) is False
    assert (
        _is_usable_settings_blob(
            {
                'agent_settings': {'llm': {'model': 'openai/x'}},
                'conversation_settings': {},
            }
        )
        is True
    )


def test_lean_create_forces_plaintext_for_tunnel_via_analytics(monkeypatch):
    """trycloudflare UI blob must land on ANALYTICS_LLM with plaintext key."""
    import json

    from proxy import _lean_conversation_create_body

    class _S:
        analytics_llm_base_url = 'http://192.168.1.196:11434/v1'
        analytics_llm_model = 'qwen3-16k-nothink:latest'
        analytics_llm_api_key = 'ollama'

    monkeypatch.setattr('config.get_settings', lambda: _S())
    body = {
        'secrets_encrypted': True,
        'agent_settings': {
            'llm': {
                'model': 'openai/old',
                'base_url': 'https://old.trycloudflare.com/v1',
                'api_key': 'gAAAAAencrypted-key',
            },
            'tools': ['terminal'],
            'agent_context': {},
        },
    }
    blob = {
        'agent_settings': {
            'llm': {
                'model': 'openai/nemotron',
                'base_url': 'https://x.trycloudflare.com/v1',
                'api_key': '**********',
            }
        }
    }
    out = json.loads(
        _lean_conversation_create_body(json.dumps(body).encode(), blob).decode()
    )
    llm = out['agent_settings']['llm']
    assert out.get('secrets_encrypted') is False
    assert llm['api_key'] == 'ollama'
    assert '11434' in llm['base_url']


def test_rewrite_clears_fernet_on_local_ollama():
    from proxy import _rewrite_llm_from_ui_blob

    agent = {
        'llm': {
            'model': 'qwen',
            'base_url': 'http://192.168.1.196:11434/v1',
            'api_key': 'gAAAAAencrypted',
        }
    }
    assert _rewrite_llm_from_ui_blob(agent, None) is True
    assert agent['llm']['api_key'] == 'ollama'
    assert agent['llm']['model'].startswith('openai/')

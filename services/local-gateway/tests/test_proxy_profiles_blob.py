"""Regression: LLM profile list must not be served from a stale per-user blob.

Creates/updates go to ``/api/profiles/{name}`` and forward to agent-server, but
the gateway used to cache ``GET /api/profiles`` in ``user_settings_blobs``.
After a successful create the UI still saw the old list.
"""

from __future__ import annotations

from proxy import (
    _blob_kind_for_path,
    _gateway_blocks_forward,
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

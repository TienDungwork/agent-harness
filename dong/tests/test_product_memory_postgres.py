"""Agent Postgres init + Qdrant long-term (không còn bảng user_memories)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infra.memory.agent_schema import load_agent_storage_ddl
from src.infra.memory.db import (
    AgentStorageError,
    get_memory_connection,
    init_agent_storage,
    is_postgres_configured,
)


def test_is_postgres_configured(monkeypatch):
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_host", "agent_postgres")
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_user", "atin")
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_password", "secret")
    assert is_postgres_configured() is True

    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_host", "")
    assert is_postgres_configured() is False


def test_get_memory_connection_unconfigured_raises(monkeypatch):
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_host", "")
    with pytest.raises(AgentStorageError, match="Agent DB chưa cấu hình"):
        with get_memory_connection():
            pass


def test_init_agent_storage_runs_ddl(monkeypatch):
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_host", "localhost")
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_user", "atin")
    monkeypatch.setattr("src.infra.memory.db.settings.agent_db_password", "secret")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    ddl = load_agent_storage_ddl()
    assert "DROP TABLE IF EXISTS user_memories" in ddl
    assert "CREATE TABLE IF NOT EXISTS human_feedback" in ddl

    with patch("psycopg2.connect", return_value=mock_conn):
        assert init_agent_storage() is True
        mock_cursor.execute.assert_called_once_with(ddl)

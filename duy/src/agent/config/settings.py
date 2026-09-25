from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "qwen3-16k-nothink"
    llm_api_key: str = "ollama"

    # Remote OpenAI-compatible (vd. 192.168.1.198:8080)
    llm_remote_base_url: str = ""
    llm_remote_model: str = ""
    llm_remote_api_key: str = ""
    llm_remote_label: str = "Remote · qwen3:4b (192.168.1.198)"
    llm_default_profile: str = "remote-4b"

    db_host: str = "192.168.1.200"
    db_port: int = 18644
    db_user: str = "vinhdq"
    db_password: str = ""

    query_timeout_seconds: int = 10
    connect_timeout_seconds: int = 10
    max_rows: int = 200
    max_result_bytes: int = 1_048_576
    sql_repair_max: int = 2

    searxng_url: str = "http://127.0.0.1:8889"
    searxng_language: str = "vi-VN"
    searxng_timeout_seconds: int = 12
    searxng_max_results: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()

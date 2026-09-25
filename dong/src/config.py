"""Cấu hình — đọc từ biến môi trường / file .env. Điểm DUY NHẤT đọc secrets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_env_bool(value: object) -> object:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(value, int):
        return value != 0
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── LLM Backend ──────────────────────────────────────────────────────────
    # "openai" = OpenAI Cloud | "self_hosted" = vLLM qua gateway OpenAI-compatible
    llm_backend: str = Field(default="openai", alias="LLM_BACKEND")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    openai_api_keys: str = Field(default="", alias="OPENAI_API_KEYS")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_request_timeout_s: float = Field(default=60.0, alias="LLM_REQUEST_TIMEOUT_S")

    # vLLM gateway (khi LLM_BACKEND=self_hosted)
    model_base_url: str = Field(default="http://192.168.1.196:18083/v1", alias="MODEL_BASE_URL")
    model_name: str = Field(default="qwen3-4b", alias="MODEL_NAME")
    model_api_key: str = Field(default="", alias="MODEL_API_KEY")
    model_endpoint: str = Field(default="http://192.168.1.196:18083/v1/chat/completions", alias="MODEL_ENDPOINT")

    # Bước "Answer" (diễn giải số liệu -> câu tiếng Việt)
    answer_use_llm: bool = Field(default=True, alias="ANSWER_USE_LLM")

    # v7 text-to-SQL / QueryPlan repair loop
    sql_repair_max: int = Field(default=2, alias="SQL_REPAIR_MAX")

    # v7 text-to-SQL generate max tokens (tight cap to prevent runaway reasoning loops)
    sql_generate_max_tokens: int = Field(default=384, alias="SQL_GENERATE_MAX_TOKENS")
    sql_respond_max_tokens: int = Field(default=1024, alias="SQL_RESPOND_MAX_TOKENS")

    # v5 Docs YAML corpus (duy style)
    docs_root: str = Field(default="resource/docs/vms_yaml", alias="DOCS_ROOT")
    memory_ttl_seconds: int = Field(default=300, alias="MEMORY_TTL_SECONDS")

    # Memory layers — MEMORY_ENABLED=false tắt cả 3 lớp (short / long / TTL)
    memory_enabled: bool = Field(default=True, alias="MEMORY_ENABLED")
    memory_short_term_enabled: bool = Field(default=True, alias="MEMORY_SHORT_TERM_ENABLED")
    memory_long_term_enabled: bool = Field(default=True, alias="MEMORY_LONG_TERM_ENABLED")

    # ── Database Nguồn Thống Kê (Postgres, Read-Only) ─────────────────────────
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_name_its: str = Field(default="its", alias="DB_NAME_ITS")
    db_name_fence: str = Field(default="virtual_fence", alias="DB_NAME_FENCE")
    db_name_face: str = Field(default="smart_face", alias="DB_NAME_FACE")
    db_name_fire: str = Field(default="firesmoke", alias="DB_NAME_FIRE")
    db_name_anomaly: str = Field(default="anomaly", alias="DB_NAME_ANOMALY")
    db_organization_id: int = Field(default=0, alias="DB_ORGANIZATION_ID")
    db_timezone: str = Field(default="Asia/Ho_Chi_Minh", alias="DB_TIMEZONE")
    db_query_timeout_s: float = Field(default=5.0, alias="DB_QUERY_TIMEOUT_S")
    db_max_rows: int = Field(default=200, alias="DB_MAX_ROWS")

    # ── ClickHouse analytics (READ-ONLY) ───────────────────────────────────────────
    ch_host: str = Field(default="", alias="CH_HOST")
    ch_port: int = Field(default=8123, alias="CH_PORT")
    ch_user: str = Field(default="", alias="CH_USER")
    ch_password: str = Field(default="", alias="CH_PASSWORD")
    ch_database: str = Field(default="", alias="CH_DATABASE")

    # ── Guardrails ───────────────────────────────────────────────────────────
    guardrails_min_answer_len: int = Field(default=5, alias="GUARDRAILS_MIN_ANSWER_LEN")
    guardrails_max_answer_len: int = Field(default=2000, alias="GUARDRAILS_MAX_ANSWER_LEN")

    # ── Observability (Langfuse Tracing Self-hosted) ─────────────────────────
    monitoring_enabled: bool = Field(default=False, alias="MONITORING_ENABLED")
    langfuse_public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="http://localhost:3000", alias="LANGFUSE_HOST")

    # ── Cache / TTL response cache (trước graph) ─────────────────────────────
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_ttl_s: int = Field(default=60, alias="CACHE_TTL_S")

    # Rewrite + decompose (gom trong rewrite_node — bỏ LLM khi câu ngắn/đơn)
    agent_decompose_min_chars: int = Field(default=48, alias="AGENT_DECOMPOSE_MIN_CHARS")
    agent_max_sub_questions: int = Field(default=4, alias="AGENT_MAX_SUB_QUESTIONS")

    @field_validator(
        "memory_enabled",
        "memory_short_term_enabled",
        "memory_long_term_enabled",
        "cache_enabled",
        "monitoring_enabled",
        "answer_use_llm",
        mode="before",
    )
    @classmethod
    def _coerce_bool_fields(cls, value: object) -> object:
        return _parse_env_bool(value)

    @property
    def short_term_memory_enabled(self) -> bool:
        return self.memory_enabled and self.memory_short_term_enabled

    @property
    def long_term_memory_enabled(self) -> bool:
        return self.memory_enabled and self.memory_long_term_enabled

    @property
    def ttl_cache_enabled(self) -> bool:
        return self.memory_enabled and self.cache_enabled

    @ttl_cache_enabled.setter
    def ttl_cache_enabled(self, value: bool) -> None:
        self.cache_enabled = value

    @property
    def api_keys(self) -> list[str]:
        return [k.strip() for k in self.openai_api_keys.split(",") if k.strip()]

    @property
    def effective_base_url(self) -> str | None:
        """Trả về base_url phù hợp cho client LLM tuỳ theo llm_backend."""
        if self.llm_backend == "self_hosted":
            return self.model_base_url or None
        if self.llm_base_url:
            return self.llm_base_url
        return None

    @property
    def effective_model(self) -> str:
        """Trả về tên model tuỳ theo llm_backend."""
        if self.llm_backend == "self_hosted":
            return self.model_name or "qwen3-4b"
        return self.llm_model or "gpt-4o-mini"

    @property
    def db_configured(self) -> bool:
        return bool(self.db_host and self.db_user)

    @property
    def effective_docs_root(self) -> Path:
        """Thư mục chứa tài liệu YAML VMS (index.yaml + cards)."""
        raw = self.docs_root or "resource/docs/vms_yaml"
        p = Path(raw)
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            p = (project_root / p).resolve()
        if p.exists() and (p / "index.yaml").exists():
            return p
        duy_path = Path(__file__).resolve().parent.parent.parent / "duy" / "VMS_doc" / "VMS_documentation"
        if duy_path.exists():
            return duy_path.resolve()
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

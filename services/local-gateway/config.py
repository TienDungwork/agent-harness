from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    host: str = '0.0.0.0'
    port: int = 18110

    # Auth: "local" = SQLite users (no Docker). "keycloak" = Keycloak compose.
    auth_backend: str = 'local'

    # Keycloak (only when auth_backend=keycloak)
    keycloak_url: str = 'http://127.0.0.1:18180'
    keycloak_realm: str = 'creanova'
    keycloak_client_id: str = 'creanova-local'
    keycloak_client_secret: str = 'creanova-local-secret'

    # Session cookie
    session_secret: str = 'change-me-creanova-local-session-secret'
    session_cookie_name: str = 'creanova_local_session'
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    cookie_samesite: str = 'lax'

    # Upstream agent-server
    agent_server_url: str = 'http://127.0.0.1:18000'
    agent_server_api_key: str = ''

    # Local DB
    database_url: str = 'sqlite:////tmp/creanova-local-gateway.db'

    # Credits (Milestone 2)
    credit_cost_per_run: float = 1.0
    credit_cost_per_conversation: float = 1.0

    # Infra credential encryption (Fernet). Generate:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    infra_encryption_key: str = ''

    # Shared token for agent harness → gateway infra APIs (X-Creanova-Infra-Token).
    # Empty disables token auth (cookie session only).
    infra_agent_token: str = ''

    # ClickHouse VMS warehouse (read-only analytics). Empty password disables.
    ch_url: str = ''
    ch_user: str = 'vms_ro'
    ch_password: str = ''
    ch_database: str = 'vms'

    # Beszel integration (shared volume written by beszel-bootstrap container)
    beszel_shared_path: str = '/beszel_shared'
    beszel_agent_port: int = 45876
    beszel_agent_port_base: int = 45000
    beszel_hub_url: str = 'http://beszel:8090'
    # Agents on other machines send metrics here (LAN URL of the hub).
    beszel_hub_public_url: str = 'http://192.168.1.191:18090'
    beszel_user_email: str = 'admin@creanova.local'
    beszel_user_password: str = 'admin123'

    # CORS / frontend origins (include Beszel UI for pin buttons)
    cors_origins: str = (
        'http://127.0.0.1:18010,http://localhost:18010,'
        'http://127.0.0.1:3001,http://localhost:3001,'
        'http://192.168.1.191:18010,'
        'http://127.0.0.1:18090,http://localhost:18090,'
        'http://192.168.1.191:18090'
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]

    @property
    def keycloak_token_url(self) -> str:
        return (
            f'{self.keycloak_url.rstrip("/")}/realms/{self.keycloak_realm}'
            '/protocol/openid-connect/token'
        )

    @property
    def keycloak_userinfo_url(self) -> str:
        return (
            f'{self.keycloak_url.rstrip("/")}/realms/{self.keycloak_realm}'
            '/protocol/openid-connect/userinfo'
        )

    @property
    def keycloak_logout_url(self) -> str:
        return (
            f'{self.keycloak_url.rstrip("/")}/realms/{self.keycloak_realm}'
            '/protocol/openid-connect/logout'
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

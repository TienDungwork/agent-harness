from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    pg_host: str
    pg_port: int = 18644
    pg_user: str
    pg_password: str

    ch_url: str = 'http://127.0.0.1:18123'
    ch_user: str = 'vms_sync'
    ch_password: str
    ch_database: str = 'vms'

    poll_seconds: int = 60
    batch_size: int = 20000
    lag_seconds: int = 30
    ch_ready_timeout_seconds: int = 300

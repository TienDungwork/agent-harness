"""AI module configuration — re-exports settings from backend.config."""

from backend.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]

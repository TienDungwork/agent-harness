"""UI / ops HTTP routes (sessions, memory, meta, feedback, auth)."""

from src.api.routers.web_backend.routes_auth import router as auth_router
from src.api.routers.web_backend.routes_feedback import router as feedback_router
from src.api.routers.web_backend.routes_memory import router as memory_router
from src.api.routers.web_backend.routes_meta import router as meta_router
from src.api.routers.web_backend.routes_sessions import router as sessions_router

__all__ = [
    "auth_router",
    "feedback_router",
    "memory_router",
    "meta_router",
    "sessions_router",
]

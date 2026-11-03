"""FastAPI routers."""

from src.api.routers.routes_agent import ask, chat, router as agent_router, stream_agent
from src.api.routers.routes_feedback import router as feedback_router
from src.api.routers.routes_memory import router as memory_router
from src.api.routers.routes_meta import router as meta_router
from src.api.routers.routes_sessions import router as sessions_router

__all__ = [
    "agent_router",
    "feedback_router",
    "memory_router",
    "meta_router",
    "sessions_router",
    "chat",
    "ask",
    "stream_agent",
]

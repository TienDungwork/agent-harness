"""FastAPI app — entry point phục vụ API + static UI.

Chạy dev server:
    uvicorn backend.main:app --reload --port 8000
    (hoặc uvicorn src.main:app --reload --port 8000)

Mở docs tương tác: http://localhost:8000/docs
"""

from backend.main import (
    AskRequest,
    AskResponse,
    ChatRequest,
    ChatResponse,
    app,
)

__all__ = ["app", "AskRequest", "AskResponse", "ChatRequest", "ChatResponse"]

"""Meta: health, models, config, LLM ping."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.shared.config import settings
from src.infra.llm import ping as llm_ping

router = APIRouter(tags=["meta"])


@router.get("/api/health")
@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "agent_ATIN v3 Backend",
        "llm_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "db_configured": settings.db_configured,
        "monitoring_enabled": settings.monitoring_enabled,
    }


@router.get("/api/models")
def get_available_models():
    return {
        "active_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "supported_models": [
            {"id": "gpt-4o-mini", "name": "OpenAI Cloud (gpt-4o-mini)", "provider": "openai"},
            {
                "id": "qwen3-4b",
                "name": "Self-hosted Qwen3-4B",
                "provider": "self_hosted",
                "endpoint": settings.model_base_url,
            },
        ],
    }


@router.get("/api/llm/ping")
def ping_llm():
    try:
        status = llm_ping()
        return {
            "status": status,
            "backend": settings.llm_backend,
            "model": settings.effective_model,
            "base_url": settings.effective_base_url or "",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/api/config")
def get_config():
    return {
        "llm_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "self_hosted_endpoint": settings.model_base_url,
        "self_hosted_model": settings.model_name,
        "monitoring_enabled": settings.monitoring_enabled,
        "supported_domains": [
            "Phương tiện (ITS)", "Vùng cấm (Fence)", "Khuôn mặt (Face)", "Ẩu đả (Fight)",
            "Đám đông (Crowd)", "Leo trèo (Intrusion)", "Cháy khói (Fire)", "Mực nước (Water)",
        ],
    }

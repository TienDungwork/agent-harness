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
    supported = [
        {"id": "gpt-4o-mini", "name": "OpenAI Cloud (gpt-4o-mini)", "provider": "openai"},
    ]
    if settings.llm_backend == "self_hosted":
        from src.infra.llm.gateway import fetch_gateway_catalog, gateway_model_ids

        catalog = fetch_gateway_catalog()
        limits = catalog.get("limits") or {}
        endpoint = settings.model_endpoint or f"{settings.model_base_url.rstrip('/')}/chat/completions"
        for mid in gateway_model_ids():
            supported.append({
                "id": mid,
                "name": f"Gateway ({mid})",
                "provider": "self_hosted",
                "endpoint": endpoint,
                "limits": limits,
            })
        if not gateway_model_ids():
            supported.append({
                "id": settings.model_name,
                "name": f"Gateway ({settings.model_name})",
                "provider": "self_hosted",
                "endpoint": endpoint,
            })
    return {
        "active_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "chat_completions_endpoint": settings.model_endpoint,
        "supported_models": supported,
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
        "self_hosted_base_url": settings.model_base_url,
        "self_hosted_chat_endpoint": settings.model_endpoint,
        "self_hosted_model": settings.model_name,
        "monitoring_enabled": settings.monitoring_enabled,
        "supported_domains": [
            "Phương tiện (ITS)", "Vùng cấm (Fence)", "Khuôn mặt (Face)", "Ẩu đả (Fight)",
            "Đám đông (Crowd)", "Leo trèo (Intrusion)", "Cháy khói (Fire)", "Mực nước (Water)",
        ],
    }

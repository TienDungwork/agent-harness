from __future__ import annotations

from contextlib import asynccontextmanager

from config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from proxy import router as proxy_router
from routers.analytics import router as analytics_router
from routers.auth import router as auth_router
from routers.conversations import router as conversations_router
from routers.credits import router as credits_router
from routers.infra import router as infra_router
from routers.ssh_ws import router as ssh_ws_router
from storage.models import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_db(settings.database_url)
    if (settings.auth_backend or 'local').strip().lower() == 'local':
        from storage.models import SessionLocal
        from storage.users import seed_local_users

        assert SessionLocal is not None
        db = SessionLocal()
        try:
            seed_local_users(db, admin_password=settings.local_admin_password or None)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title='Creanova Local Gateway', version='0.1.0', lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.include_router(auth_router)
    app.include_router(credits_router)
    app.include_router(conversations_router)
    app.include_router(infra_router)
    app.include_router(analytics_router)
    app.include_router(ssh_ws_router)
    # Proxy last so specific routers win.
    app.include_router(proxy_router)

    @app.get('/healthz')
    async def healthz() -> dict[str, str]:
        return {'status': 'ok'}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        'main:app',
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == '__main__':
    main()

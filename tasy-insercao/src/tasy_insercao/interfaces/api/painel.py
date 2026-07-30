from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tasy_insercao.infrastructure.auth.portal_auth import ensure_admin_seed
from tasy_insercao.infrastructure.config.logging import get_logger, setup_logging
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.interfaces.api.routers import auth as auth_router
from tasy_insercao.interfaces.api.routers import cadastros as cadastros_router
from tasy_insercao.interfaces.api.routers import filas as filas_router
from tasy_insercao.interfaces.api.routers import integracoes as integracoes_router
from tasy_insercao.interfaces.api.routers import reprocessar as reprocessar_router
from tasy_insercao.interfaces.api.routers import scheduler as scheduler_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    try:
        ensure_admin_seed()
        logger.info("Portal API pronta | admin seed ok")
    except Exception as exc:
        logger.warning("Portal seed admin falhou (rode db up?): %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Portal Stone → Tasy",
        description=(
            "API do portal de controle: autenticação, integrações (Postgres staging) e filas RabbitMQ. "
            "Front React em /portal-controle."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.portal_cors_origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "portal-stone-tasy",
            "env": settings.APP_ENV,
            "postgres": bool(settings.POSTGRES_DB),
        }

    app.include_router(auth_router.router)
    app.include_router(integracoes_router.router)
    app.include_router(filas_router.router)
    app.include_router(cadastros_router.router)
    app.include_router(reprocessar_router.router)
    app.include_router(scheduler_router.router)
    return app


app = create_app()

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from tasy_insercao.infrastructure.auth.portal_auth import (
    decode_token,
    ensure_admin_seed,
    get_user_by_id,
)
from tasy_insercao.infrastructure.config.logging import get_logger, setup_logging
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.interfaces.api.routers import audit as audit_router
from tasy_insercao.interfaces.api.routers import auth as auth_router
from tasy_insercao.interfaces.api.routers import cadastros as cadastros_router
from tasy_insercao.interfaces.api.routers import filas as filas_router
from tasy_insercao.interfaces.api.routers import integracoes as integracoes_router
from tasy_insercao.interfaces.api.routers import purge as purge_router
from tasy_insercao.interfaces.api.routers import reprocessar as reprocessar_router
from tasy_insercao.interfaces.api.routers import scheduler as scheduler_router
from tasy_insercao.interfaces.api.routers.audit import registrar_api_acesso

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

    @app.middleware("http")
    async def audit_mutations(request: Request, call_next):
        response = await call_next(request)
        try:
            if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
                return response
            auth = request.headers.get("Authorization") or ""
            user_ctx = None
            if auth.lower().startswith("bearer "):
                try:
                    payload = decode_token(auth.split(" ", 1)[1].strip())
                    row = get_user_by_id(int(payload["sub"]))
                    if row and row.get("ie_ativo") == "S":
                        user_ctx = {
                            "nr_sequencia": row["nr_sequencia"],
                            "ds_login": row["ds_login"],
                        }
                except Exception:
                    user_ctx = None
            if user_ctx:
                registrar_api_acesso(
                    request=request,
                    user=user_ctx,
                    status_code=int(response.status_code),
                )
        except Exception:
            logger.debug("Falha ao registrar auditoria de API", exc_info=True)
        return response

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
    app.include_router(purge_router.router)
    app.include_router(audit_router.router)
    app.include_router(scheduler_router.router)
    return app


app = create_app()

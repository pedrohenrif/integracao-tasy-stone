from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from tasy_insercao.infrastructure.auth.portal_acao_log import listar_acao_logs, registrar_acao_log
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.interfaces.api.deps import AdminUser

router = APIRouter(prefix="/api/audit", tags=["audit"])


class SistemaAuditBody(BaseModel):
    acao: str = Field(min_length=1, max_length=80)
    obs: str | None = None
    depois: dict[str, Any] | None = None


@router.post("/sistema")
async def api_audit_sistema(
    body: SistemaAuditBody,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """Recebe eventos do stone-extracao (scheduler). Protegido por token interno."""
    expected = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not expected or (x_internal_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Token interno inválido")
    registrar_acao_log(
        user_id=None,
        login="sistema",
        acao=body.acao.strip()[:80],
        obs=(body.obs or "")[:500] or None,
        depois=body.depois,
    )
    return {"ok": True}


@router.get("/logs")
async def api_audit_logs(
    _user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    acao: str | None = Query(default=None),
    login: str | None = Query(default=None),
    id_stone: str | None = Query(default=None),
    data_de: date | None = Query(default=None),
    data_ate: date | None = Query(default=None),
):
    try:
        return listar_acao_logs(
            limit=limit,
            offset=offset,
            acao=acao,
            login=login,
            id_stone=id_stone,
            data_de=data_de,
            data_ate=data_ate,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def registrar_api_acesso(
    *,
    request: Request,
    user: dict[str, Any] | None,
    status_code: int,
) -> None:
    """Registra mutações autenticadas (POST/PUT/PATCH/DELETE) na auditoria."""
    if user is None:
        return
    method = request.method.upper()
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    path = request.url.path
    skip_prefixes = (
        "/api/auth/login",
        "/api/audit/sistema",
        "/interno/",
        "/health",
    )
    if path.startswith(skip_prefixes) or path == "/api/auth/login":
        return
    # Evita duplicar logs muito específicos que já gravam detalhe
    # (ainda registra o acesso HTTP genérico para rastreio).
    login = str(user.get("ds_login") or user.get("login") or "?")
    user_id = user.get("nr_sequencia") or user.get("id")
    try:
        user_id_int = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id_int = None
    registrar_acao_log(
        user_id=user_id_int,
        login=login,
        acao=f"api_{method.lower()}",
        obs=f"{method} {path} → {status_code}"[:500],
        depois={"method": method, "path": path, "status_code": status_code},
    )

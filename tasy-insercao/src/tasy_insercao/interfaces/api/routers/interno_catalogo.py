from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.persistence.catalog_queries import listar_seriais_ativos

router = APIRouter(prefix="/interno", tags=["interno-catalogo"])


def _require_internal_token(x_internal_token: str | None) -> None:
    expected = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not expected or (x_internal_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Token interno inválido")


@router.get("/seriais-ativos")
async def api_seriais_ativos(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """Seriais com ie_status=A — usado pela extração Stone no lugar do .env."""
    _require_internal_token(x_internal_token)
    return {"seriais": listar_seriais_ativos()}

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.persistence.movimento_stone import upsert_movimentos

router = APIRouter(prefix="/interno/movimentos-stone", tags=["interno-movimentos"])


def _require_internal_token(x_internal_token: str | None) -> None:
    expected = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not expected or (x_internal_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Token interno inválido")


class MovimentoStoneIn(BaseModel):
    origem: str
    id_stone: str
    nr_serie_maquininha: str | None = None
    vl_transacao: str | float | None = None
    dt_movimentacao: str | None = None
    reference_date: str | None = None
    status_origem: str | None = None
    operation: str | None = None
    publicado: str | bool = "N"
    ds_motivo: str | None = None
    source: str | None = None


class MovimentosStoneBody(BaseModel):
    items: list[MovimentoStoneIn] = Field(default_factory=list, max_length=5000)


@router.post("")
async def api_upsert_movimentos(
    body: MovimentosStoneBody,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    _require_internal_token(x_internal_token)
    payload: list[dict[str, Any]] = []
    for item in body.items:
        publicado = item.publicado
        if isinstance(publicado, bool):
            publicado = "S" if publicado else "N"
        payload.append(
            {
                "origem": item.origem,
                "id_stone": item.id_stone,
                "nr_serie_maquininha": item.nr_serie_maquininha,
                "vl_transacao": item.vl_transacao,
                "dt_movimentacao": item.dt_movimentacao,
                "reference_date": item.reference_date,
                "status_origem": item.status_origem,
                "operation": item.operation,
                "publicado": publicado,
                "ds_motivo": item.ds_motivo,
                "source": item.source,
            }
        )
    n = upsert_movimentos(payload)
    return {"ok": True, "upserted": n}

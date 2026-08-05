from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tasy_insercao.infrastructure.persistence.catalog_queries import (
    atualizar_mapeamento,
    criar_mapeamento,
    listar_bandeiras,
    listar_mapeamentos,
    listar_maquininhas,
    listar_tipos,
    seriais_com_erro_cadastro,
    upsert_bandeira,
    upsert_maquininha,
)
from tasy_insercao.infrastructure.persistence.debug_queries import listar_caixas
from tasy_insercao.interfaces.api.deps import AdminUser

router = APIRouter(prefix="/api/cadastros", tags=["cadastros"])


def _ser(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat(sep=" ", timespec="seconds")
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class MaquininhaBody(BaseModel):
    nr_serie_maquininha: str = Field(min_length=1, max_length=64)
    cd_caixa: int
    cd_transacao_financeira: int
    ds_maquininha: str | None = None
    ie_status: str = "A"


class MapeamentoBody(BaseModel):
    cd_cartao_bandeira_tasy: int
    cd_tipo_transacao: int
    cd_bandeira: int | None = None


class BandeiraBody(BaseModel):
    cd_bandeira: int
    ds_bandeira: str = Field(min_length=1, max_length=50)


@router.get("/maquininhas")
async def get_maquininhas(_user: AdminUser):
    try:
        return {
            "items": [_ser(x) for x in listar_maquininhas()],
            "seriais_pendentes": seriais_com_erro_cadastro(),
            "caixas": listar_caixas(),
        }
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/maquininhas")
async def post_maquininha(_user: AdminUser, body: MaquininhaBody):
    try:
        row = upsert_maquininha(
            nr_serie_maquininha=body.nr_serie_maquininha,
            cd_caixa=body.cd_caixa,
            cd_transacao_financeira=body.cd_transacao_financeira,
            ds_maquininha=body.ds_maquininha,
            ie_status=body.ie_status,
        )
        return _ser(row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mapeamentos")
async def get_mapeamentos(_user: AdminUser):
    try:
        return {
            "items": [_ser(x) for x in listar_mapeamentos()],
            "tipos": listar_tipos(),
            "bandeiras": listar_bandeiras(),
        }
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/mapeamentos")
async def post_mapeamento(_user: AdminUser, body: MapeamentoBody):
    try:
        row = criar_mapeamento(
            cd_cartao_bandeira_tasy=body.cd_cartao_bandeira_tasy,
            cd_tipo_transacao=body.cd_tipo_transacao,
            cd_bandeira=body.cd_bandeira,
        )
        return _ser(row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/mapeamentos/{nr_sequencia}")
async def put_mapeamento(_user: AdminUser, nr_sequencia: int, body: MapeamentoBody):
    try:
        row = atualizar_mapeamento(
            nr_sequencia,
            cd_cartao_bandeira_tasy=body.cd_cartao_bandeira_tasy,
            cd_tipo_transacao=body.cd_tipo_transacao,
            cd_bandeira=body.cd_bandeira,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Mapeamento não encontrado")
        return _ser(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bandeiras")
async def get_bandeiras(_user: AdminUser):
    try:
        return {"items": listar_bandeiras()}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/bandeiras")
async def post_bandeira(_user: AdminUser, body: BandeiraBody):
    try:
        return upsert_bandeira(body.cd_bandeira, body.ds_bandeira)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

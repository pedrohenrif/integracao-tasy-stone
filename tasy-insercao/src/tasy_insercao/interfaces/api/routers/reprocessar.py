from __future__ import annotations

from datetime import date

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from tasy_insercao.application.use_cases.reprocessar import (
    extrair_cartao_dia,
    importar_pix_csv,
    reprocessar_dia,
    reprocessar_registro,
    reprocessar_selecionados,
)
from tasy_insercao.infrastructure.auth.portal_acao_log import listar_acao_logs
from tasy_insercao.interfaces.api.deps import AdminUser, CurrentUser

router = APIRouter(prefix="/api/reprocessar", tags=["reprocessar"])


class ReprocessarSelecionadosBody(BaseModel):
    nr_sequencias: list[int] = Field(default_factory=list, min_length=1, max_length=200)


class ReprocessarDiaBody(BaseModel):
    """date: YYYY-MM-DD ou YYYYMMDD."""

    date: str


class ReprocessarRegistroBody(BaseModel):
    nr_sequencia: int
    nr_serie_maquininha: str | None = None
    cd_caixa: int | None = None
    obs: str | None = None


def _parse_ref_date(raw: str) -> date:
    value = (raw or "").strip()
    if len(value) == 8 and value.isdigit():
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Data inválida. Use YYYY-MM-DD ou YYYYMMDD.",
        ) from exc


@router.post("/selecionados")
async def api_reprocessar_selecionados(body: ReprocessarSelecionadosBody, user: CurrentUser):
    try:
        return await reprocessar_selecionados(body.nr_sequencias, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/dia")
async def api_reprocessar_dia(body: ReprocessarDiaBody, user: AdminUser):
    """Admin: força extração Stone do dia (cartão + solicitação PIX) via stone-extracao."""
    data_ref = _parse_ref_date(body.date)
    try:
        return await reprocessar_dia(data_ref, user=user)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pix-csv")
async def api_importar_pix_csv(
    user: AdminUser,
    date: str = Query(..., description="YYYY-MM-DD ou YYYYMMDD"),
    trigger_cartao: bool = Query(False),
    file: UploadFile = File(..., description="CSV PIX Stone"),
):
    """Admin: publica PIX a partir de CSV (dias que a Stone não reenvia via webhook)."""
    data_ref = _parse_ref_date(date)
    raw = await file.read()
    if not raw or not raw.strip():
        raise HTTPException(status_code=400, detail="Arquivo CSV vazio")
    try:
        return await importar_pix_csv(
            data_ref,
            file_bytes=raw,
            filename=file.filename or "pix.csv",
            content_type=file.content_type,
            trigger_cartao=trigger_cartao,
            user=user,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/cartao")
async def api_extrair_cartao_dia(body: ReprocessarDiaBody, user: AdminUser):
    """Admin: força extração de cartão do dia (sem solicitar PIX)."""
    data_ref = _parse_ref_date(body.date)
    try:
        return await extrair_cartao_dia(data_ref, user=user)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/registro")
async def api_reprocessar_registro(body: ReprocessarRegistroBody, user: CurrentUser):
    try:
        return await reprocessar_registro(
            body.nr_sequencia,
            user=user,
            nr_serie_maquininha=body.nr_serie_maquininha,
            cd_caixa=body.cd_caixa,
            obs=body.obs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/logs")
async def api_reprocessar_logs(
    _user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    acao: str | None = Query(default=None),
    login: str | None = Query(default=None),
    id_stone: str | None = Query(default=None),
    data_de: date | None = Query(default=None),
    data_ate: date | None = Query(default=None),
):
    """Compat: preferir GET /api/audit/logs."""
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

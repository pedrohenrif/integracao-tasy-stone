from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from tasy_insercao.application.use_cases.reprocessar import (
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
    """Admin: força extração Stone do dia (cartão) via stone-extracao."""
    data_ref = _parse_ref_date(body.date)
    try:
        return await reprocessar_dia(data_ref, user=user)
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
    limit: int = Query(default=100, ge=1, le=500),
):
    try:
        return {"items": listar_acao_logs(limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

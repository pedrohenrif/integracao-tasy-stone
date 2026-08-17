from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from tasy_insercao.application.use_cases.purge_recebimentos_stone import (
    PurgeRequest,
    confirm_purge,
    preview_purge,
)
from tasy_insercao.interfaces.api.deps import AdminUser

router = APIRouter(prefix="/api/purge", tags=["purge"])


class PurgeBody(BaseModel):
    nm_usuario: str = "stone"
    nr_sequencias: list[int] = Field(default_factory=list, max_length=100)
    id_stones: list[str] = Field(default_factory=list, max_length=100)
    cd_caixa: int | None = None
    data_de: date | None = None
    data_ate: date | None = None
    id_stone: str | None = None
    allow_fechado: bool = False


class PurgeConfirmBody(PurgeBody):
    confirm_token: str
    confirm_phrase: str


def _to_req(body: PurgeBody) -> PurgeRequest:
    return PurgeRequest(
        nm_usuario=body.nm_usuario,
        nr_sequencias=body.nr_sequencias or None,
        id_stones=body.id_stones or None,
        cd_caixa=body.cd_caixa,
        data_de=body.data_de,
        data_ate=body.data_ate,
        id_stone=body.id_stone,
        allow_fechado=body.allow_fechado,
    )


@router.post("/preview")
async def api_purge_preview(body: PurgeBody, user: AdminUser):
    """Admin: preview do que seria apagado no Oracle (sem deletar)."""
    try:
        return preview_purge(_to_req(body), user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/confirm")
async def api_purge_confirm(body: PurgeConfirmBody, user: AdminUser):
    """Admin: confirma exclusão (exige token do preview + frase EXCLUIR)."""
    try:
        return confirm_purge(
            _to_req(body),
            confirm_token=body.confirm_token,
            confirm_phrase=body.confirm_phrase,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

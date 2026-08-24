from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, HTTPException, Query

from tasy_insercao.application.use_cases.fechar_recebimentos_abertos import (
    data_ontem_iso,
    fechar_recebimentos_abertos_stone,
)
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.persistence.oracle import OracleDB, TasyOracleRepository
from tasy_insercao.interfaces.api.deps import AdminUser

logger = get_logger(__name__)

router = APIRouter(prefix="/api/tesouraria", tags=["tesouraria"])


@router.post("/fechar-recebimentos-abertos")
async def api_fechar_recebimentos_abertos_portal(
    user: AdminUser,
    dt: date_cls | None = Query(
        default=None,
        alias="date",
        description="Dia do recebimento (YYYY-MM-DD). Padrão: ontem.",
    ),
    nr_seq_caixa: int | None = Query(
        default=None,
        description="Opcional: restringe a um caixa Tasy.",
    ),
):
    """
    Admin: confirma (FECHAR) todos os recebimentos Stone ainda abertos do dia.
    Um FECHAR por caixa_receb (ex.: 1 por maquininha).
    """
    dia = dt or date_cls.fromisoformat(data_ontem_iso())
    logger.info(
        "API portal | fechar-recebimentos-abertos | user=%s | date=%s | caixa=%s",
        user.get("login") or user.get("sub"),
        dia.isoformat(),
        nr_seq_caixa,
    )
    db = OracleDB()
    try:
        tasy = TasyOracleRepository(db)
        return fechar_recebimentos_abertos_stone(
            tasy,
            dt=dia,
            nr_seq_caixa=nr_seq_caixa,
        )
    except Exception as exc:
        logger.exception("API portal | fechar-recebimentos-abertos falhou")
        raise HTTPException(status_code=500, detail=str(exc)[:500]) from exc
    finally:
        db.close()

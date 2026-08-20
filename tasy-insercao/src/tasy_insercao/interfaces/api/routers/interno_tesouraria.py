from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Header, HTTPException, Query

from tasy_insercao.application.use_cases.fechar_recebimentos_abertos import (
    data_ontem_iso,
    fechar_recebimentos_abertos_stone,
)
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.persistence.oracle import OracleDB, TasyOracleRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/interno/tesouraria", tags=["interno-tesouraria"])


def _require_internal_token(x_internal_token: str | None) -> None:
    expected = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not expected or (x_internal_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Token interno inválido")


@router.post("/fechar-recebimentos-abertos")
async def api_fechar_recebimentos_abertos(
    dt: date_cls | None = Query(
        default=None,
        alias="date",
        description="Dia do recebimento (YYYY-MM-DD). Padrão: ontem (America/Sao_Paulo).",
    ),
    nr_seq_caixa: int | None = Query(
        default=None,
        description="Opcional: restringe a um caixa Tasy.",
    ),
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """
    Confirma recebimentos Stone ainda abertos (dt_fechamento IS NULL) do dia.

    Um FECHAR por caixa_receb unificado (N cartões). Protegido por PORTAL_INTERNAL_TOKEN.
    """
    _require_internal_token(x_internal_token)
    dia = dt or date_cls.fromisoformat(data_ontem_iso())
    logger.info(
        "API interno | fechar-recebimentos-abertos | date=%s | caixa=%s",
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("API interno | fechar-recebimentos-abertos falhou")
        raise HTTPException(status_code=500, detail=str(exc)[:500]) from exc
    finally:
        db.close()

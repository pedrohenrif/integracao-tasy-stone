from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from tasy_insercao.infrastructure.persistence.debug_queries import (
    FiltrosPainel,
    listar_caixas,
    listar_registros,
    resumo,
)
from tasy_insercao.interfaces.api.deps import CurrentUser

router = APIRouter(prefix="/api", tags=["integracoes"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value: str | int | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filtros_from_query(
    data_de: str | None,
    data_ate: str | None,
    cd_caixa: str | int | None,
    cd_status: str | int | None,
    tipo: str | None,
    id_stone: str | None,
    nr_serie: str | None,
    autorizacao: str | None,
    bandeira: str | None,
    ie_internacional: str | None,
    vl_min: str | None,
    vl_max: str | None,
    obs: str | None,
    limit: int,
    offset: int,
) -> FiltrosPainel:
    return FiltrosPainel(
        data_de=_parse_date(data_de),
        data_ate=_parse_date(data_ate),
        cd_caixa=_parse_int(cd_caixa),
        cd_status=_parse_int(cd_status),
        cd_tipo_transacao=tipo or None,
        id_stone=id_stone or None,
        nr_serie=nr_serie or None,
        cd_autorizacao=autorizacao or None,
        cd_bandeira=bandeira or None,
        ie_internacional=ie_internacional or None,
        vl_min=_parse_decimal(vl_min),
        vl_max=_parse_decimal(vl_max),
        obs=obs or None,
        limit=limit,
        offset=offset,
    )


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
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


@router.get("/caixas")
async def api_caixas(_user: CurrentUser):
    try:
        return {"items": listar_caixas()}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/registros")
async def api_registros(
    _user: CurrentUser,
    data_de: str | None = None,
    data_ate: str | None = None,
    cd_caixa: str | None = None,
    cd_status: str | None = None,
    tipo: str | None = None,
    id_stone: str | None = None,
    nr_serie: str | None = None,
    autorizacao: str | None = None,
    bandeira: str | None = None,
    ie_internacional: str | None = None,
    vl_min: str | None = None,
    vl_max: str | None = None,
    obs: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    f = _filtros_from_query(
        data_de, data_ate, cd_caixa, cd_status, tipo, id_stone, nr_serie,
        autorizacao, bandeira, ie_internacional, vl_min, vl_max, obs, limit, offset,
    )
    try:
        rows = listar_registros(f)
        summary = resumo(f)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return {
        "filtros": _serialize_row(dict(f.__dict__)),
        "resumo": {
            "totais": _serialize_row(summary["totais"]),
            "por_status": [_serialize_row(x) for x in summary["por_status"]],
            "por_caixa": [_serialize_row(x) for x in summary["por_caixa"]],
        },
        "registros": [_serialize_row(r) for r in rows],
    }

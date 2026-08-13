from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from tasy_insercao.domain.integracao.models import (
    EventoFilaCartao,
    EventoFilaPix,
    StatusIntegracao,
    TipoTransacaoCartao,
    TransacaoCartao,
    TransacaoPix,
)
from tasy_insercao.infrastructure.auth.portal_acao_log import registrar_acao_log
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.messaging.rabbit import (
    RetryPublisher,
    connect_rabbitmq,
    declare_topology,
)
from tasy_insercao.infrastructure.persistence.debug_queries import (
    atualizar_registro_reprocesso,
    atualizar_status_registro,
    listar_registros_por_ids,
)

logger = get_logger(__name__)

_STATUS_REPROCESSAVEIS = {
    StatusIntegracao.ERRO_RETRY.value,
    StatusIntegracao.ERRO_DEFINITIVO.value,
    StatusIntegracao.SEM_TESOURARIA.value,
    StatusIntegracao.CONFIRMACAO_PENDENTE.value,
}


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00").split("+")[0])
    raise ValueError(f"Data inválida: {value!r}")


def _tipo_enum(raw: str | None) -> TipoTransacaoCartao:
    key = (raw or "unknown").strip().lower()
    try:
        return TipoTransacaoCartao(key)
    except ValueError:
        return TipoTransacaoCartao.UNKNOWN


def _snapshot_registro(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "nr_sequencia": row.get("nr_sequencia"),
        "id_stone": row.get("id_stone"),
        "nr_serie_maquininha": row.get("nr_serie_maquininha"),
        "cd_caixa": row.get("cd_caixa"),
        "cd_status": row.get("cd_status"),
        "cd_tipo_transacao": row.get("cd_tipo_transacao"),
        "vl_transacao": float(row["vl_transacao"]) if row.get("vl_transacao") is not None else None,
        "ds_obs_processo": row.get("ds_obs_processo"),
    }


def _evento_from_registro(row: dict[str, Any]) -> tuple[Any, str]:
    """Monta evento da fila a partir do staging. Retorna (evento, fluxo)."""
    tipo = _tipo_enum(row.get("cd_tipo_transacao"))
    now = datetime.now()
    dt_mov = _as_datetime(row["dt_movimentacao"])
    vl = Decimal(str(row["vl_transacao"] or 0))
    parcelada = str(row.get("ie_transacao_parcelada") or "N").upper() == "S"
    qt = int(row.get("qt_parcelas") or 1)

    if tipo == TipoTransacaoCartao.PIX:
        tx = TransacaoPix(
            id_stone=row["id_stone"],
            e2e_id=row.get("cd_autorizacao"),
            vl_transacao=vl,
            dt_movimentacao=dt_mov,
            nr_serie_maquininha=row["nr_serie_maquininha"],
            reference_date=dt_mov.strftime("%Y%m%d"),
        )
        evento = EventoFilaPix(
            source="portal.reprocess",
            received_at=now,
            attempt=1,
            first_seen_at=now,
            last_error=None,
            transaction=tx,
        )
        return evento, "pix"

    tx = TransacaoCartao(
        id_stone=row["id_stone"],
        vl_transacao=vl,
        dt_movimentacao=dt_mov,
        nr_serie_maquininha=row["nr_serie_maquininha"],
        cd_autorizacao=row.get("cd_autorizacao"),
        qt_parcelas=qt,
        ie_transacao_parcelada=parcelada or qt > 1,
        cd_tipo_transacao=tipo,
        cd_bandeira=row.get("cd_bandeira"),
        reference_date=dt_mov.strftime("%Y%m%d"),
    )
    evento = EventoFilaCartao(
        source="portal.reprocess",
        received_at=now,
        attempt=1,
        first_seen_at=now,
        last_error=None,
        transaction=tx,
    )
    return evento, "cartao"


def _user_meta(user: dict[str, Any] | None) -> tuple[int | None, str]:
    if not user:
        return None, "sistema"
    return user.get("nr_sequencia"), str(user.get("ds_login") or "desconhecido")


async def reprocessar_selecionados(
    nr_sequencias: list[int],
    *,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ids = sorted({int(x) for x in nr_sequencias if x})
    if not ids:
        return {"enfileirados": 0, "ignorados": [], "erros": [], "detail": "Nenhum id informado"}
    if len(ids) > 200:
        raise ValueError("Máximo 200 registros por vez")

    rows = listar_registros_por_ids(ids)
    by_id = {int(r["nr_sequencia"]): r for r in rows}
    ignorados: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []
    publicados: list[str] = []
    user_id, login = _user_meta(user)

    conn = await connect_rabbitmq()
    try:
        channel = await conn.channel()
        await declare_topology(channel)
        publisher = RetryPublisher(channel)

        for nr in ids:
            row = by_id.get(nr)
            if not row:
                erros.append({"nr_sequencia": nr, "erro": "Registro não encontrado"})
                continue
            status = int(row["cd_status"])
            if status == StatusIntegracao.INTEGRADO.value:
                ignorados.append(
                    {
                        "nr_sequencia": nr,
                        "id_stone": row["id_stone"],
                        "motivo": "Já integrado (status 5)",
                    }
                )
                continue
            if status not in _STATUS_REPROCESSAVEIS and status not in (
                StatusIntegracao.PENDENTE.value,
                StatusIntegracao.PROCESSANDO.value,
            ):
                # permite pendente/processando se vier no lote; erros 6/7 são o foco
                pass
            try:
                antes = _snapshot_registro(row)
                evento, fluxo = _evento_from_registro(row)
                await publisher.publish_main(evento, fluxo=fluxo)
                obs = "Reprocessamento em lote solicitado pelo portal"
                atualizar_status_registro(nr, StatusIntegracao.PENDENTE.value, obs)
                depois = {**antes, "cd_status": StatusIntegracao.PENDENTE.value, "ds_obs_processo": obs}
                registrar_acao_log(
                    user_id=user_id,
                    login=login,
                    acao="reprocessar_lote",
                    nr_seq_registro=nr,
                    id_stone=row.get("id_stone"),
                    antes=antes,
                    depois=depois,
                    obs=obs,
                )
                publicados.append(row["id_stone"])
            except Exception as exc:
                logger.exception("Falha ao reprocessar nr=%s", nr)
                erros.append(
                    {
                        "nr_sequencia": nr,
                        "id_stone": row.get("id_stone"),
                        "erro": str(exc)[:300],
                    }
                )
    finally:
        await conn.close()

    return {
        "enfileirados": len(publicados),
        "ids_stone": publicados,
        "ignorados": ignorados,
        "erros": erros,
    }


async def reprocessar_registro(
    nr_sequencia: int,
    *,
    user: dict[str, Any],
    nr_serie_maquininha: str | None = None,
    cd_caixa: int | None = None,
    obs: str | None = None,
) -> dict[str, Any]:
    """Edita serial/caixa (opcional) e reenfileira um registro com status 6/7."""
    rows = listar_registros_por_ids([nr_sequencia])
    if not rows:
        raise ValueError(f"Registro {nr_sequencia} não encontrado")
    row = rows[0]
    status = int(row["cd_status"])
    if status == StatusIntegracao.INTEGRADO.value:
        raise ValueError("Já integrado (status 5) — não pode reprocessar")
    if status not in _STATUS_REPROCESSAVEIS:
        raise ValueError(
            f"Status {status} não permite reprocesso com edição. Use status 6, 7, 8 ou 9."
        )

    antes = _snapshot_registro(row)
    serial = (nr_serie_maquininha or "").strip() or None
    obs_final = (obs or "").strip() or "Reprocessamento individual solicitado pelo portal"

    atualizado = atualizar_registro_reprocesso(
        nr_sequencia,
        nr_serie_maquininha=serial,
        cd_caixa=cd_caixa,
        cd_status=StatusIntegracao.PENDENTE.value,
        obs=obs_final,
    )
    if not atualizado:
        raise RuntimeError("Falha ao atualizar registro no staging")

    depois = _snapshot_registro(atualizado)
    user_id, login = _user_meta(user)

    conn = await connect_rabbitmq()
    try:
        channel = await conn.channel()
        await declare_topology(channel)
        publisher = RetryPublisher(channel)
        evento, fluxo = _evento_from_registro(atualizado)
        await publisher.publish_main(evento, fluxo=fluxo)
    finally:
        await conn.close()

    registrar_acao_log(
        user_id=user_id,
        login=login,
        acao="reprocessar_registro",
        nr_seq_registro=nr_sequencia,
        id_stone=atualizado.get("id_stone"),
        antes=antes,
        depois=depois,
        obs=obs_final,
    )

    return {
        "enfileirado": True,
        "fluxo": fluxo,
        "nr_sequencia": nr_sequencia,
        "id_stone": atualizado.get("id_stone"),
        "antes": antes,
        "depois": depois,
        "mensagem": "Registro atualizado e reenfileirado",
    }


async def reprocessar_dia(
    data_ref: date,
    *,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Chama stone-extracao:
    1) POST /cartao/conciliation?date=YYYYMMDD
    2) POST /pix/conciliation/request?date=YYYY-MM-DD
    """
    ymd = data_ref.strftime("%Y%m%d")
    iso = data_ref.strftime("%Y-%m-%d")
    base = settings.STONE_EXTRACAO_BASE_URL.rstrip("/")
    url_cartao = f"{base}/cartao/conciliation"
    url_pix = f"{base}/pix/conciliation/request"
    user_id, login = _user_meta(user)

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(url_cartao, params={"date": ymd})
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"stone-extracao inacessível em {base}: {exc}. "
                "Verifique se o serviço está no ar (:8000)."
            ) from exc

        if resp.status_code >= 400:
            detail = resp.text[:800]
            try:
                err_json = resp.json()
                detail = str(err_json.get("detail") or detail)
            except Exception:
                pass
            registrar_acao_log(
                user_id=user_id,
                login=login,
                acao="reprocessar_dia_erro",
                id_stone=None,
                antes=None,
                depois={
                    "reference_date": ymd,
                    "http_status": resp.status_code,
                    "detail": detail[:500],
                },
                obs=f"Erro Stone/extração cartão {ymd}: {detail[:300]}",
            )
            raise RuntimeError(f"stone-extracao HTTP {resp.status_code}: {detail}") from None

        body = resp.json()

        pix_body: dict[str, Any] = {}
        pix_error: str | None = None
        logger.info(
            "reprocessar_dia | PIX request | date=%s | url=%s",
            iso,
            url_pix,
        )
        try:
            resp_pix = await client.post(url_pix, params={"date": iso})
            if resp_pix.status_code >= 400:
                detail_pix = resp_pix.text[:800]
                try:
                    err_pix = resp_pix.json()
                    detail_pix = str(err_pix.get("detail") or detail_pix)
                except Exception:
                    pass
                pix_error = f"HTTP {resp_pix.status_code}: {detail_pix}"
                logger.error(
                    "reprocessar_dia | PIX falhou | date=%s | http=%s | detail=%s",
                    iso,
                    resp_pix.status_code,
                    detail_pix[:400],
                )
            else:
                pix_body = resp_pix.json()
                logger.info(
                    "reprocessar_dia | PIX ok | date=%s | status=%s | msg=%s",
                    iso,
                    pix_body.get("status"),
                    str(pix_body.get("message") or "")[:200],
                )
        except httpx.RequestError as exc:
            pix_error = f"stone-extracao PIX inacessível: {exc}"
            logger.exception("reprocessar_dia | PIX request error | date=%s", iso)

    parsed = body.get("parsed_count")
    published = body.get("published_count")
    stone_msg = body.get("message")
    pix_status = pix_body.get("status") if pix_body else None
    pix_msg = pix_body.get("message") if pix_body else pix_error

    obs = f"Republicação {ymd} | cartão published={published}"
    if pix_error:
        obs = f"{obs} | PIX erro={pix_error[:120]}"
    elif pix_status:
        obs = f"{obs} | PIX status={pix_status}"
    if stone_msg:
        obs = f"{obs} | {stone_msg}"
    registrar_acao_log(
        user_id=user_id,
        login=login,
        acao="reprocessar_dia",
        id_stone=None,
        antes=None,
        depois={
            "reference_date": ymd,
            "parsed_count": parsed,
            "published_count": published,
            "raw_bytes": body.get("raw_bytes"),
            "message": stone_msg,
            "parse_stats": body.get("parse_stats"),
            "pix_reference_date": iso,
            "pix_status": pix_status,
            "pix_message": pix_msg,
            "pix_error": pix_error,
        },
        obs=obs[:500],
    )
    if published == 0 and stone_msg:
        mensagem = stone_msg
    else:
        mensagem = (
            "Dia republicado na fila (cartão). Registros já integrados (status 5) "
            "são ignorados pelo consumer."
        )
    if pix_error:
        mensagem = f"{mensagem} PIX: falha — {pix_error}"
    elif pix_msg:
        mensagem = f"{mensagem} PIX: {pix_msg}"

    return {
        "reference_date": body.get("reference_date", ymd),
        "parsed_count": parsed,
        "published_count": published,
        "queue": body.get("queue"),
        "source": body.get("source"),
        "mode": body.get("mode"),
        "raw_bytes": body.get("raw_bytes"),
        "stone_message": stone_msg,
        "parse_stats": body.get("parse_stats") or {},
        "xml_backup_path": body.get("xml_backup_path"),
        "totais_avisos": body.get("totais_avisos") or [],
        "stone_extracao_url": url_cartao,
        "mensagem": mensagem,
        "pix": {
            "reference_date": iso,
            "status": pix_status,
            "message": pix_body.get("message") if pix_body else None,
            "source": pix_body.get("source") if pix_body else None,
            "published_from_body": pix_body.get("published_from_body") if pix_body else 0,
            "error": pix_error,
        },
    }

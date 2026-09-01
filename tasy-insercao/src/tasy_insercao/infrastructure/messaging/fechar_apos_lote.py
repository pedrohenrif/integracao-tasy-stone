from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from urllib.request import urlopen

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)

# Quiet period por caixa_receb: remarca a cada cartao/PIX; FECHAR apos o lote assentar.
_pending: dict[int, asyncio.Task] = {}
_adiamentos: dict[int, int] = {}


def cancel_fechar_recebimento(nr_seq_caixa_rec: int) -> None:
    nr = int(nr_seq_caixa_rec)
    old = _pending.pop(nr, None)
    _adiamentos.pop(nr, None)
    if old and not old.done():
        old.cancel()
        logger.info("FECHAR apos lote | cancelado | caixa_receb=%s", nr)


def _parse_date(dt_recebimento: str) -> date:
    raw = str(dt_recebimento)[:10]
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _status_lote_pix(iso_date: str) -> dict[str, Any] | None:
    """Consulta stone-extracao: webhook PIX do dia ja chegou?"""
    base = (settings.STONE_EXTRACAO_BASE_URL or "").rstrip("/")
    if not base:
        return None
    url = f"{base}/lote/status?date={iso_date}"
    try:
        with urlopen(url, timeout=5) as resp:  # noqa: S310 — URL interna configurada
            import json

            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("FECHAR apos lote | lote status indisponivel | %s | %s", url, exc)
        return None


def _motivo_adiar_fechar(
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
) -> str | None:
    """
    None = pode FECHAR.
    str = motivo para remarcar o quiet period.
    """
    if not settings.FECHAR_REQUIRE_STAGING_OK and not settings.FECHAR_REQUIRE_LOTE_PIX_OK:
        return None

    from tasy_insercao.infrastructure.persistence.debug_queries import (
        contar_incompletos_dia_caixa,
    )
    from tasy_insercao.infrastructure.persistence.oracle import OracleDB, TasyOracleRepository

    dt = _parse_date(dt_recebimento)
    iso = dt.isoformat()

    cd_caixa: int | None = None
    if settings.FECHAR_REQUIRE_STAGING_OK:
        try:
            tasy = TasyOracleRepository(OracleDB())
            cd_caixa = tasy.get_nr_seq_caixa_de_receb(nr_seq_caixa_rec)
        except Exception:
            logger.exception(
                "FECHAR apos lote | falha ao resolver caixa | caixa_receb=%s",
                nr_seq_caixa_rec,
            )
            return "falha ao resolver caixa do recebimento"

        if cd_caixa is None:
            return f"caixa nao encontrado para recebimento={nr_seq_caixa_rec}"

        try:
            counts = contar_incompletos_dia_caixa(dt, cd_caixa)
        except Exception:
            logger.exception(
                "FECHAR apos lote | falha ao ler staging | caixa=%s | date=%s",
                cd_caixa,
                iso,
            )
            return "falha ao consultar staging"
        incompletos = int(counts.get("incompletos") or 0)
        if incompletos > 0:
            return (
                f"staging incompleto caixa={cd_caixa} date={iso} "
                f"incompletos={incompletos} pix_incompletos={counts.get('pix_incompletos')} "
                f"ok={counts.get('ok')} dlq={counts.get('dlq')}"
            )

    if settings.FECHAR_REQUIRE_LOTE_PIX_OK:
        lote = _status_lote_pix(iso)
        if lote is not None:
            awaiting = bool(lote.get("awaiting_webhook"))
            webhook_at = lote.get("webhook_at")
            if awaiting and not webhook_at:
                return f"aguardando webhook PIX do dia {iso}"

    return None


def schedule_fechar_apos_lote(
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
    confirmar_fn: Callable[[int, str], Any],
    serial: str | None = None,
    fluxo: str = "cartao",
) -> None:
    """
    Agenda FECHAR do recebimento unificado (1 por caixa) apos quiet period.

    Antes de confirmar:
    - confere staging do caixa/dia (sem pendente/retry/processando);
    - se o lote PIX ainda aguarda webhook, adia;
    - remarcam o timer (com teto FECHAR_MAX_ADIAMENTOS).
    """
    if not settings.FECHAR_APOS_LOTE_ENABLED:
        return

    delay = max(1, int(settings.FECHAR_APOS_LOTE_SECONDS or 300))
    nr = int(nr_seq_caixa_rec)
    dt = str(dt_recebimento)[:10]
    is_adiado = str(fluxo).startswith("adiado:")

    old = _pending.get(nr)
    if old and not old.done():
        old.cancel()
        logger.info(
            "FECHAR apos lote | remarcado | caixa_receb=%s | serial=%s | fluxo=%s | delay=%ss",
            nr,
            serial or "-",
            fluxo,
            delay,
        )
    else:
        logger.info(
            "FECHAR apos lote | agendado | caixa_receb=%s | serial=%s | fluxo=%s | delay=%ss",
            nr,
            serial or "-",
            fluxo,
            delay,
        )

    # Novo insert (cartao/PIX) zera contador de adiamentos; remarque por gate nao.
    if not is_adiado:
        _adiamentos[nr] = 0

    async def _run() -> None:
        try:
            await asyncio.sleep(delay)
            motivo = await asyncio.to_thread(
                _motivo_adiar_fechar,
                nr_seq_caixa_rec=nr,
                dt_recebimento=dt,
            )
            if motivo:
                n_adiado = int(_adiamentos.get(nr, 0)) + 1
                max_ad = max(0, int(settings.FECHAR_MAX_ADIAMENTOS or 0))
                _adiamentos[nr] = n_adiado
                if n_adiado <= max_ad:
                    logger.warning(
                        "FECHAR apos lote | adiado (%s/%s) | caixa_receb=%s | %s",
                        n_adiado,
                        max_ad,
                        nr,
                        motivo,
                    )
                    schedule_fechar_apos_lote(
                        nr_seq_caixa_rec=nr,
                        dt_recebimento=dt,
                        confirmar_fn=confirmar_fn,
                        serial=serial,
                        fluxo=f"adiado:{fluxo}",
                    )
                    return
                logger.error(
                    "FECHAR apos lote | forçando apos %s adiamentos | caixa_receb=%s | %s",
                    n_adiado,
                    nr,
                    motivo,
                )

            logger.info(
                "FECHAR apos lote | executando | caixa_receb=%s | serial=%s | dt=%s",
                nr,
                serial or "-",
                dt,
            )
            await asyncio.to_thread(confirmar_fn, nr, dt)
            _adiamentos.pop(nr, None)
            logger.info(
                "FECHAR apos lote | ok | caixa_receb=%s | serial=%s",
                nr,
                serial or "-",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "FECHAR apos lote | falha | caixa_receb=%s | serial=%s",
                nr,
                serial or "-",
            )
        finally:
            cur = _pending.get(nr)
            if cur is asyncio.current_task():
                _pending.pop(nr, None)

    _pending[nr] = asyncio.create_task(_run())


def pending_fechar_count() -> int:
    return sum(1 for t in _pending.values() if t and not t.done())

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)

# Quiet period por caixa_receb: remarca a cada cartao/PIX; FECHAR apos o lote assentar.
_pending: dict[int, asyncio.Task] = {}


def cancel_fechar_recebimento(nr_seq_caixa_rec: int) -> None:
    nr = int(nr_seq_caixa_rec)
    old = _pending.pop(nr, None)
    if old and not old.done():
        old.cancel()
        logger.info("FECHAR apos lote | cancelado | caixa_receb=%s", nr)


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

    Cartao e PIX no mesmo caixa_receb remarcam o mesmo timer — so confirma
    depois que as duas filas pararam de inserir nesse recebimento.
    """
    if not settings.FECHAR_APOS_LOTE_ENABLED:
        return

    delay = max(1, int(settings.FECHAR_APOS_LOTE_SECONDS or 300))
    nr = int(nr_seq_caixa_rec)
    dt = str(dt_recebimento)[:10]

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

    async def _run() -> None:
        try:
            await asyncio.sleep(delay)
            logger.info(
                "FECHAR apos lote | executando | caixa_receb=%s | serial=%s | dt=%s",
                nr,
                serial or "-",
                dt,
            )
            await asyncio.to_thread(confirmar_fn, nr, dt)
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

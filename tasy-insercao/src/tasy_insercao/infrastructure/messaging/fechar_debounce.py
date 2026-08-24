from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)

# Debounce: após o último cartão da maquininha (mesmo caixa_receb), confirma o recebimento.
_pending: dict[int, asyncio.Task] = {}


def schedule_fechar_recebimento(
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
    confirmar_fn: Callable[[int, str], Any],
    serial: str | None = None,
) -> None:
    """
    Agenda FECHAR deste caixa_receb após quiet period.
    Novo cartão no mesmo recebimento cancela e remarca o timer.
    """
    if not settings.FECHAR_RECEB_DEBOUNCE_ENABLED:
        return

    delay = max(1, int(settings.FECHAR_RECEB_DEBOUNCE_SECONDS or 120))
    nr = int(nr_seq_caixa_rec)
    dt = str(dt_recebimento)[:10]

    old = _pending.get(nr)
    if old and not old.done():
        old.cancel()
        logger.info(
            "FECHAR debounce | remarcado | caixa_receb=%s | serial=%s | delay=%ss",
            nr,
            serial or "-",
            delay,
        )
    else:
        logger.info(
            "FECHAR debounce | agendado | caixa_receb=%s | serial=%s | delay=%ss",
            nr,
            serial or "-",
            delay,
        )

    async def _run() -> None:
        try:
            await asyncio.sleep(delay)
            logger.info(
                "FECHAR debounce | executando | caixa_receb=%s | serial=%s | dt=%s",
                nr,
                serial or "-",
                dt,
            )
            await asyncio.to_thread(confirmar_fn, nr, dt)
            logger.info(
                "FECHAR debounce | ok | caixa_receb=%s | serial=%s",
                nr,
                serial or "-",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "FECHAR debounce | falha | caixa_receb=%s | serial=%s",
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

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)

# Quiet period: fecha o recebimento atual após o último cartão da maquininha.
# Na troca de serial o FECHAR é imediato (ensure); isto cobre o *último* do caixa.
_pending: dict[int, asyncio.Task] = {}


def cancel_fechar_recebimento(nr_seq_caixa_rec: int) -> None:
    """Cancela timer pendente (ex.: já FECHOU na troca de serial)."""
    nr = int(nr_seq_caixa_rec)
    old = _pending.pop(nr, None)
    if old and not old.done():
        old.cancel()
        logger.info("FECHAR quiet | cancelado | caixa_receb=%s", nr)


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
    if not settings.FECHAR_ULTIMO_RECEB_ENABLED:
        return

    delay = max(1, int(settings.FECHAR_ULTIMO_RECEB_SECONDS or 120))
    nr = int(nr_seq_caixa_rec)
    dt = str(dt_recebimento)[:10]

    old = _pending.get(nr)
    if old and not old.done():
        old.cancel()
        logger.info(
            "FECHAR quiet | remarcado | caixa_receb=%s | serial=%s | delay=%ss",
            nr,
            serial or "-",
            delay,
        )
    else:
        logger.info(
            "FECHAR quiet | agendado | caixa_receb=%s | serial=%s | delay=%ss",
            nr,
            serial or "-",
            delay,
        )

    async def _run() -> None:
        try:
            await asyncio.sleep(delay)
            logger.info(
                "FECHAR quiet | executando | caixa_receb=%s | serial=%s | dt=%s",
                nr,
                serial or "-",
                dt,
            )
            await asyncio.to_thread(confirmar_fn, nr, dt)
            logger.info(
                "FECHAR quiet | ok | caixa_receb=%s | serial=%s",
                nr,
                serial or "-",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "FECHAR quiet | falha | caixa_receb=%s | serial=%s",
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

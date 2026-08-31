from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from aio_pika.abc import AbstractChannel

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def _mensagens_prontas(channel: AbstractChannel, queue_name: str) -> int | None:
    """Retorna messages_ready da fila, ou None se nao conseguir ler."""
    try:
        q = await channel.declare_queue(queue_name, durable=True, passive=True)
        result = getattr(q, "declaration_result", None)
        if result is None:
            return None
        return int(getattr(result, "message_count", 0) or 0)
    except Exception:
        logger.exception("Falha ao consultar fila | queue=%s", queue_name)
        return None


async def fechar_se_filas_vazias(
    channel: AbstractChannel,
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
    confirmar_fn: Callable[[int, str], Any],
    serial: str | None = None,
) -> bool:
    """
    FECHAR o recebimento unificado (1 por caixa) quando cartao e PIX nao tem msgs prontas.

    Assim o lote fecha no fim (sem timer) e PIX/cartao no mesmo caixa_receb nao
    dispara FECHAR enquanto a outra fila ainda tem trabalho.
    """
    if not settings.FECHAR_ULTIMO_RECEB_ENABLED:
        return False

    ready_cartao = await _mensagens_prontas(channel, settings.RABBITMQ_QUEUE_CARTAO)
    ready_pix = await _mensagens_prontas(channel, settings.RABBITMQ_QUEUE_PIX)
    if ready_cartao is None or ready_pix is None:
        return False

    if ready_cartao > 0 or ready_pix > 0:
        logger.info(
            "FECHAR unificado | filas ainda tem msgs | cartao=%s | pix=%s | "
            "caixa_receb=%s | serial=%s",
            ready_cartao,
            ready_pix,
            nr_seq_caixa_rec,
            serial or "-",
        )
        return False

    logger.info(
        "FECHAR unificado | filas vazias | executando | caixa_receb=%s | serial=%s | dt=%s",
        nr_seq_caixa_rec,
        serial or "-",
        dt_recebimento,
    )
    try:
        await asyncio.to_thread(
            confirmar_fn, int(nr_seq_caixa_rec), str(dt_recebimento)[:10]
        )
        logger.info(
            "FECHAR unificado | ok | caixa_receb=%s | serial=%s",
            nr_seq_caixa_rec,
            serial or "-",
        )
        return True
    except Exception:
        logger.exception(
            "FECHAR unificado | falha | caixa_receb=%s | serial=%s",
            nr_seq_caixa_rec,
            serial or "-",
        )
        return False


# Alias legado (worker / testes antigos)
async def fechar_se_fila_cartao_vazia(
    channel: AbstractChannel,
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
    confirmar_fn: Callable[[int, str], Any],
    serial: str | None = None,
) -> bool:
    return await fechar_se_filas_vazias(
        channel,
        nr_seq_caixa_rec=nr_seq_caixa_rec,
        dt_recebimento=dt_recebimento,
        confirmar_fn=confirmar_fn,
        serial=serial,
    )

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from aio_pika.abc import AbstractChannel

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def _mensagens_prontas_cartao(channel: AbstractChannel) -> int | None:
    """Retorna messages_ready da fila de cartao, ou None se nao conseguir ler."""
    queue_name = settings.RABBITMQ_QUEUE_CARTAO
    try:
        q = await channel.declare_queue(queue_name, durable=True, passive=True)
        result = getattr(q, "declaration_result", None)
        if result is None:
            return None
        return int(getattr(result, "message_count", 0) or 0)
    except Exception:
        logger.exception("Falha ao consultar fila | queue=%s", queue_name)
        return None


async def fechar_se_fila_cartao_vazia(
    channel: AbstractChannel,
    *,
    nr_seq_caixa_rec: int,
    dt_recebimento: str,
    confirmar_fn: Callable[[int, str], Any],
    serial: str | None = None,
) -> bool:
    """
    FECHAR o recebimento atual quando a fila de cartao nao tem mais msgs prontas.

    - Troca de serial: FECHAR imediato no ensure (outro recebimento).
    - Ultimo serial do lote: FECHAR aqui, sem espera de N minutos.
    """
    if not settings.FECHAR_ULTIMO_RECEB_ENABLED:
        return False

    ready = await _mensagens_prontas_cartao(channel)
    if ready is None:
        return False
    if ready > 0:
        logger.info(
            "FECHAR ultimo | fila ainda tem msgs | ready=%s | caixa_receb=%s | serial=%s",
            ready,
            nr_seq_caixa_rec,
            serial or "-",
        )
        return False

    logger.info(
        "FECHAR ultimo | fila vazia | executando | caixa_receb=%s | serial=%s | dt=%s",
        nr_seq_caixa_rec,
        serial or "-",
        dt_recebimento,
    )
    try:
        await asyncio.to_thread(
            confirmar_fn, int(nr_seq_caixa_rec), str(dt_recebimento)[:10]
        )
        logger.info(
            "FECHAR ultimo | ok | caixa_receb=%s | serial=%s",
            nr_seq_caixa_rec,
            serial or "-",
        )
        return True
    except Exception:
        logger.exception(
            "FECHAR ultimo | falha | caixa_receb=%s | serial=%s",
            nr_seq_caixa_rec,
            serial or "-",
        )
        return False

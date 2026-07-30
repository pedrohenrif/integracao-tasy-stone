from __future__ import annotations

import json
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def connect_rabbitmq(url: str | None = None) -> AbstractRobustConnection:
    connection = await aio_pika.connect_robust(url or settings.RABBITMQ_URL)
    logger.info("RabbitMQ conectado | insercao")
    return connection


async def _declare_flow(
    channel: AbstractChannel,
    exchange: aio_pika.Exchange,
    main_name: str,
    retry_name: str,
    dlq_name: str,
) -> dict[str, aio_pika.abc.AbstractQueue]:
    main_q = await channel.declare_queue(main_name, durable=True)
    await main_q.bind(exchange, routing_key=main_name)

    retry_q = await channel.declare_queue(
        retry_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.RABBITMQ_EXCHANGE,
            "x-dead-letter-routing-key": main_name,
        },
    )
    await retry_q.bind(exchange, routing_key=retry_name)

    dlq = await channel.declare_queue(dlq_name, durable=True)
    await dlq.bind(exchange, routing_key=dlq_name)
    return {"main": main_q, "retry": retry_q, "dlq": dlq}


async def declare_topology(channel: AbstractChannel) -> dict[str, Any]:
    """
    Topologia Cartão + PIX (filas separadas, mesma exchange).
    """
    exchange = await channel.declare_exchange(
        settings.RABBITMQ_EXCHANGE, ExchangeType.DIRECT, durable=True
    )
    cartao = await _declare_flow(
        channel,
        exchange,
        settings.RABBITMQ_QUEUE_CARTAO,
        settings.RABBITMQ_QUEUE_RETRY,
        settings.RABBITMQ_QUEUE_DLQ,
    )
    pix = await _declare_flow(
        channel,
        exchange,
        settings.RABBITMQ_QUEUE_PIX,
        settings.RABBITMQ_QUEUE_PIX_RETRY,
        settings.RABBITMQ_QUEUE_PIX_DLQ,
    )
    return {"cartao": cartao, "pix": pix}


class RetryPublisher:
    def __init__(self, channel: AbstractChannel) -> None:
        self.channel = channel

    async def _publish(self, routing_key: str, payload: dict, headers: dict, expiration_ms: int | None = None) -> None:
        message = Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=expiration_ms,
            headers=headers,
        )
        exchange = await self.channel.get_exchange(settings.RABBITMQ_EXCHANGE)
        await exchange.publish(message, routing_key=routing_key)

    async def publish_retry(self, evento: Any, delay_seconds: int, *, fluxo: str = "cartao") -> None:
        retry_q = (
            settings.RABBITMQ_QUEUE_PIX_RETRY if fluxo == "pix" else settings.RABBITMQ_QUEUE_RETRY
        )
        id_stone = evento.transaction.id_stone
        await self._publish(
            retry_q,
            evento.model_dump(mode="json"),
            {
                "x-attempt": evento.attempt,
                "x-delay-seconds": delay_seconds,
                "x-flow": fluxo,
                "x-last-error": (evento.last_error or "")[:200],
            },
            expiration_ms=delay_seconds * 1000,
        )
        logger.info(
            "Retry agendado | fluxo=%s | id_stone=%s | attempt=%s | delay=%ss",
            fluxo,
            id_stone,
            evento.attempt,
            delay_seconds,
        )

    async def publish_dlq(self, evento: Any, *, fluxo: str = "cartao") -> None:
        dlq = settings.RABBITMQ_QUEUE_PIX_DLQ if fluxo == "pix" else settings.RABBITMQ_QUEUE_DLQ
        await self._publish(
            dlq,
            evento.model_dump(mode="json"),
            {"x-attempt": evento.attempt, "x-dlq": True, "x-flow": fluxo},
        )
        logger.error(
            "DLQ | fluxo=%s | id_stone=%s | attempt=%s | error=%s",
            fluxo,
            evento.transaction.id_stone,
            evento.attempt,
            evento.last_error,
        )

    async def publish_main(self, evento: Any, *, fluxo: str = "cartao") -> None:
        """Republica na fila principal (reprocessamento manual / portal)."""
        main_q = settings.RABBITMQ_QUEUE_PIX if fluxo == "pix" else settings.RABBITMQ_QUEUE_CARTAO
        await self._publish(
            main_q,
            evento.model_dump(mode="json"),
            {"x-attempt": evento.attempt, "x-flow": fluxo, "x-reprocess": True},
        )
        logger.info(
            "Reprocessamento enfileirado | fluxo=%s | id_stone=%s",
            fluxo,
            evento.transaction.id_stone,
        )


def delay_for_attempt(attempt: int) -> int:
    delays = settings.retry_delays
    idx = min(max(attempt - 1, 0), len(delays) - 1)
    return delays[idx]


async def close_rabbitmq(connection: AbstractRobustConnection | None) -> None:
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ desconectado | insercao")

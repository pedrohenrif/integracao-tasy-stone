from __future__ import annotations

import json
from datetime import datetime, timezone

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection

from tasy_insercao.domain.integracao.models import EventoFilaCartao
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def connect_rabbitmq(url: str | None = None) -> AbstractRobustConnection:
    connection = await aio_pika.connect_robust(url or settings.RABBITMQ_URL)
    logger.info("RabbitMQ conectado | insercao")
    return connection


async def declare_topology(channel: AbstractChannel) -> dict[str, aio_pika.abc.AbstractQueue]:
    """
    Topologia:
      - stone.cartao.transactions       (principal)
      - stone.cartao.transactions.retry (TTL → volta à principal)
      - stone.cartao.transactions.dlq   (erros definitivos / max attempts)
    """
    exchange = await channel.declare_exchange(
        settings.RABBITMQ_EXCHANGE, ExchangeType.DIRECT, durable=True
    )

    main_q = await channel.declare_queue(settings.RABBITMQ_QUEUE_CARTAO, durable=True)
    await main_q.bind(exchange, routing_key=settings.RABBITMQ_QUEUE_CARTAO)

    # Retry: mensagem expira e é dead-lettered de volta para a fila principal
    retry_args = {
        "x-dead-letter-exchange": settings.RABBITMQ_EXCHANGE,
        "x-dead-letter-routing-key": settings.RABBITMQ_QUEUE_CARTAO,
    }
    retry_q = await channel.declare_queue(
        settings.RABBITMQ_QUEUE_RETRY,
        durable=True,
        arguments=retry_args,
    )
    await retry_q.bind(exchange, routing_key=settings.RABBITMQ_QUEUE_RETRY)

    dlq = await channel.declare_queue(settings.RABBITMQ_QUEUE_DLQ, durable=True)
    await dlq.bind(exchange, routing_key=settings.RABBITMQ_QUEUE_DLQ)

    return {"main": main_q, "retry": retry_q, "dlq": dlq}


class RetryPublisher:
    def __init__(self, channel: AbstractChannel) -> None:
        self.channel = channel

    async def publish_retry(self, evento: EventoFilaCartao, delay_seconds: int) -> None:
        body = json.dumps(evento.model_dump(mode="json"), default=str).encode("utf-8")
        message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            expiration=delay_seconds * 1000,  # ms — TTL na mensagem
            headers={
                "x-attempt": evento.attempt,
                "x-delay-seconds": delay_seconds,
                "x-last-error": (evento.last_error or "")[:200],
            },
        )
        exchange = await self.channel.get_exchange(settings.RABBITMQ_EXCHANGE)
        await exchange.publish(message, routing_key=settings.RABBITMQ_QUEUE_RETRY)
        logger.info(
            "Retry agendado | id_stone=%s | attempt=%s | delay=%ss",
            evento.transaction.id_stone,
            evento.attempt,
            delay_seconds,
        )

    async def publish_dlq(self, evento: EventoFilaCartao) -> None:
        body = json.dumps(evento.model_dump(mode="json"), default=str).encode("utf-8")
        message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={"x-attempt": evento.attempt, "x-dlq": True},
        )
        exchange = await self.channel.get_exchange(settings.RABBITMQ_EXCHANGE)
        await exchange.publish(message, routing_key=settings.RABBITMQ_QUEUE_DLQ)
        logger.error(
            "DLQ | id_stone=%s | attempt=%s | error=%s",
            evento.transaction.id_stone,
            evento.attempt,
            evento.last_error,
        )


def delay_for_attempt(attempt: int) -> int:
    delays = settings.retry_delays
    idx = min(max(attempt - 1, 0), len(delays) - 1)
    return delays[idx]


async def close_rabbitmq(connection: AbstractRobustConnection | None) -> None:
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ desconectado | insercao")

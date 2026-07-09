from __future__ import annotations

import json
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from stone_extracao.domain.cartao.models import EventoFilaCartao
from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def connect_rabbitmq(url: str | None = None) -> AbstractRobustConnection:
    connection = await aio_pika.connect_robust(url or settings.RABBITMQ_URL)
    logger.info("RabbitMQ conectado | extracao")
    return connection


async def declare_topology(channel: AbstractChannel) -> None:
    exchange = await channel.declare_exchange(
        settings.RABBITMQ_EXCHANGE, ExchangeType.DIRECT, durable=True
    )
    queue = await channel.declare_queue(settings.RABBITMQ_QUEUE_CARTAO, durable=True)
    await queue.bind(exchange, routing_key=settings.RABBITMQ_QUEUE_CARTAO)


class RabbitPublisher:
    def __init__(self, channel: AbstractChannel) -> None:
        self.channel = channel

    async def publish_cartao(self, evento: EventoFilaCartao) -> None:
        await declare_topology(self.channel)
        body = json.dumps(evento.model_dump(mode="json"), default=str).encode("utf-8")
        message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={"x-attempt": evento.attempt},
        )
        exchange = await self.channel.get_exchange(settings.RABBITMQ_EXCHANGE)
        await exchange.publish(message, routing_key=settings.RABBITMQ_QUEUE_CARTAO)
        logger.info(
            "Enfileirado | cartao | id_stone=%s | attempt=%s",
            evento.transaction.id_stone,
            evento.attempt,
        )


async def close_rabbitmq(connection: AbstractRobustConnection | None) -> None:
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ desconectado | extracao")

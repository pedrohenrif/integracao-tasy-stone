from __future__ import annotations

import json

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from stone_extracao.domain.cartao.models import EventoFilaCartao
from stone_extracao.domain.pix.models import EventoFilaPix
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
    for queue_name in (settings.RABBITMQ_QUEUE_CARTAO, settings.RABBITMQ_QUEUE_PIX):
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, routing_key=queue_name)


class RabbitPublisher:
    def __init__(self, channel: AbstractChannel) -> None:
        self.channel = channel

    async def _publish(self, routing_key: str, payload: dict, headers: dict | None = None) -> None:
        await declare_topology(self.channel)
        message = Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=headers or {},
        )
        exchange = await self.channel.get_exchange(settings.RABBITMQ_EXCHANGE)
        await exchange.publish(message, routing_key=routing_key)

    async def publish_cartao(self, evento: EventoFilaCartao) -> None:
        await self._publish(
            settings.RABBITMQ_QUEUE_CARTAO,
            evento.model_dump(mode="json"),
            {"x-attempt": evento.attempt, "x-flow": "cartao"},
        )
        logger.info(
            "Enfileirado | cartao | id_stone=%s | attempt=%s",
            evento.transaction.id_stone,
            evento.attempt,
        )

    async def publish_pix(self, evento: EventoFilaPix) -> None:
        await self._publish(
            settings.RABBITMQ_QUEUE_PIX,
            evento.model_dump(mode="json"),
            {"x-attempt": evento.attempt, "x-flow": "pix"},
        )
        logger.info(
            "Enfileirado | pix | id_stone=%s | e2e=%s | attempt=%s",
            evento.transaction.id_stone,
            evento.transaction.e2e_id,
            evento.attempt,
        )


async def close_rabbitmq(connection: AbstractRobustConnection | None) -> None:
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ desconectado | extracao")

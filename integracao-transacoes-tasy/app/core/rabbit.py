from __future__ import annotations

import json
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message, RobustConnection
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def connect_rabbitmq(url: str | None = None) -> AbstractRobustConnection:
    connection = await aio_pika.connect_robust(url or settings.RABBITMQ_URL)
    logger.info("RabbitMQ conectado")
    return connection


async def declare_cartao_queue(
    channel: AbstractChannel,
    queue_name: str | None = None,
) -> aio_pika.abc.AbstractQueue:
    name = queue_name or settings.RABBITMQ_QUEUE_CARTAO
    await channel.declare_exchange("stone.direct", ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(name, durable=True)
    await queue.bind("stone.direct", routing_key=name)
    return queue


async def publish_json(
    channel: AbstractChannel,
    routing_key: str,
    payload: dict[str, Any],
    *,
    exchange_name: str = "stone.direct",
) -> None:
    body = json.dumps(payload, default=str).encode("utf-8")
    message = Message(
        body=body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    exchange = await channel.get_exchange(exchange_name)
    await exchange.publish(message, routing_key=routing_key)


async def close_rabbitmq(connection: RobustConnection | AbstractRobustConnection | None) -> None:
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ desconectado")

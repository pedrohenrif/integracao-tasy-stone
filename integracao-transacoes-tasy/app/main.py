from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_cartao import router as cartao_router
from app.api.routes_health import router as health_router
from app.core.logging import setup_logging
from app.core.rabbit import close_rabbitmq, connect_rabbitmq, declare_cartao_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await declare_cartao_queue(channel)
    app.state.rabbit_connection = connection
    app.state.rabbit_channel = channel
    yield
    await close_rabbitmq(connection)


app = FastAPI(
    title="Integracao Stone -> Tasy",
    description=(
        "Producer FastAPI: recebe extrato de cartão Stone, valida e publica no RabbitMQ. "
        "PIX e inserts Tasy ficam para fases seguintes."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(cartao_router)

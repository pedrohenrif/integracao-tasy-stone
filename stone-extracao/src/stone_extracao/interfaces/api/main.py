from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from stone_extracao.application.use_cases.extrair_conciliacao_cartao import (
    ExtrairConciliacaoCartao,
)
from stone_extracao.infrastructure.config.logging import setup_logging
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.messaging.rabbit import (
    RabbitPublisher,
    close_rabbitmq,
    connect_rabbitmq,
    declare_topology,
)
from stone_extracao.infrastructure.parsers.cartao_parser import CartaoXmlParser
from stone_extracao.infrastructure.stone.conciliation_client import (
    StoneConciliationClient,
    StoneFetchError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await declare_topology(channel)
    app.state.rabbit_connection = connection
    app.state.rabbit_channel = channel
    app.state.publisher = RabbitPublisher(channel)
    yield
    await close_rabbitmq(connection)


app = FastAPI(
    title="stone-extracao",
    description=(
        "Producer: extrai conciliação de cartão Stone, valida e publica no RabbitMQ. "
        "Não grava no Tasy. PIX fica para fase 2."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


class ConciliationResponse(BaseModel):
    reference_date: str
    source: str
    parsed_count: int
    published_count: int
    queue: str
    sample_ids: list[str] = Field(default_factory=list)


@app.get("/health")
async def health():
    token_ok = bool(settings.STONE_API_TOKEN)
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "stone_token_configured": token_ok,
        "use_sample": settings.STONE_USE_SAMPLE,
        "queue": settings.RABBITMQ_QUEUE_CARTAO,
    }


@app.post("/cartao/conciliation", response_model=ConciliationResponse)
async def ingest_cartao(
    request: Request,
    date: str = Query(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
):
    """
    Extrai extrato de cartão da Stone e publica na fila.
    Com STONE_API_TOKEN no .env usa a API real.
    Com STONE_USE_SAMPLE=true usa o XML local (dev).
    """
    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None:
        raise HTTPException(status_code=503, detail="RabbitMQ não conectado")

    use_case = ExtrairConciliacaoCartao(
        stone_client=StoneConciliationClient(),
        parser=CartaoXmlParser(),
        publisher=publisher,
    )
    try:
        result = await use_case.execute(date)
    except StoneFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ConciliationResponse(
        reference_date=result.reference_date,
        source=result.source,
        parsed_count=result.parsed_count,
        published_count=result.published_count,
        queue=settings.RABBITMQ_QUEUE_CARTAO,
        sample_ids=result.sample_ids,
    )

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rabbit import declare_cartao_queue, publish_json
from app.jobs.fetch_cartao import CartaoFetchError, fetch_conciliation_xml
from app.parsers.cartao_xml import parse_cartao_xml
from app.schemas.cartao import EventoFilaCartao

logger = get_logger(__name__)
router = APIRouter(prefix="/cartao", tags=["cartao"])


class ConciliationResponse(BaseModel):
    reference_date: str
    source: str
    parsed_count: int
    published_count: int
    queue: str
    sample_ids: list[str] = Field(default_factory=list)


async def _publish_transactions(request: Request, transactions, date: str, source: str) -> ConciliationResponse:
    channel = getattr(request.app.state, "rabbit_channel", None)
    if channel is None:
        raise HTTPException(status_code=503, detail="RabbitMQ não conectado")

    queue_name = settings.RABBITMQ_QUEUE_CARTAO
    await declare_cartao_queue(channel, queue_name)

    now = datetime.now(timezone.utc)
    published = 0
    for tx in transactions:
        evento = EventoFilaCartao(received_at=now, transaction=tx)
        await publish_json(channel, queue_name, evento.model_dump(mode="json"))
        published += 1
        logger.info(
            "Enfileirado | cartao | id_stone=%s | terminal=%s | valor=%s",
            tx.id_stone,
            tx.nr_serie_maquininha,
            tx.vl_transacao,
        )

    return ConciliationResponse(
        reference_date=date,
        source=source,
        parsed_count=len(transactions),
        published_count=published,
        queue=queue_name,
        sample_ids=[t.id_stone for t in transactions[:5]],
    )


@router.post("/conciliation", response_model=ConciliationResponse)
async def ingest_cartao_conciliation(
    request: Request,
    date: str = Query(..., pattern=r"^\d{8}$", description="Data de referência YYYYMMDD"),
    use_sample: bool = Query(
        True,
        description="Se True (default em scaffold), lê o XML local em vez da API Stone",
    ),
    sample_path: str | None = Query(
        None,
        description="Caminho opcional do XML de cartão",
    ),
):
    """
    Producer: busca/parseia extrato de cartão e publica 1 mensagem por transação no RabbitMQ.
    Não grava no Tasy.
    """
    try:
        raw = await fetch_conciliation_xml(
            date,
            use_sample=use_sample,
            sample_path=sample_path,
        )
    except CartaoFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("Recebido | cartao | date=%s | bytes=%s", date, len(raw))

    try:
        transactions = parse_cartao_xml(raw)
    except Exception as exc:
        logger.exception("Falha ao parsear XML de cartão")
        raise HTTPException(status_code=422, detail=f"XML inválido: {exc}") from exc

    logger.info("Parseado | cartao | date=%s | count=%s", date, len(transactions))
    source = "sample" if use_sample or not settings.STONE_API_TOKEN else "stone_api"
    return await _publish_transactions(request, transactions, date, source)


@router.post("/conciliation/file", response_model=ConciliationResponse)
async def ingest_cartao_from_path(
    request: Request,
    path: str = Query(..., description="Caminho do XML Conciliation"),
    date: str = Query("00000000", pattern=r"^\d{8}$"),
):
    """Atalho de dev: parseia um arquivo local e publica na fila."""
    file_path = Path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {path}")

    raw = file_path.read_bytes()
    logger.info("Recebido | cartao | fonte=file | path=%s | bytes=%s", path, len(raw))
    transactions = parse_cartao_xml(raw)
    return await _publish_transactions(request, transactions, date, "file")

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from stone_extracao.domain.cartao.models import EventoFilaCartao
from stone_extracao.domain.cartao.ports import (
    CartaoParserPort,
    ConciliationFilePort,
    MessagePublisherPort,
)
from stone_extracao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtracaoResultado:
    reference_date: str
    source: str
    parsed_count: int
    published_count: int
    sample_ids: list[str]


class ExtrairConciliacaoCartao:
    """Use case: buscar extrato Stone → parsear → publicar 1 msg/tx na fila."""

    def __init__(
        self,
        stone_client: ConciliationFilePort,
        parser: CartaoParserPort,
        publisher: MessagePublisherPort,
    ) -> None:
        self.stone_client = stone_client
        self.parser = parser
        self.publisher = publisher

    async def execute(self, reference_date: str) -> ExtracaoResultado:
        raw = await self.stone_client.fetch(reference_date)
        logger.info("Recebido | cartao | date=%s | bytes=%s", reference_date, len(raw))

        transactions = self.parser.parse(raw)
        logger.info("Parseado | cartao | date=%s | count=%s", reference_date, len(transactions))

        now = datetime.now(timezone.utc)
        published = 0
        for tx in transactions:
            evento = EventoFilaCartao(
                received_at=now,
                first_seen_at=now,
                attempt=1,
                transaction=tx,
            )
            await self.publisher.publish_cartao(evento)
            published += 1

        from stone_extracao.infrastructure.config.settings import settings

        source = "sample" if settings.STONE_USE_SAMPLE else "stone_api"
        return ExtracaoResultado(
            reference_date=reference_date,
            source=source,
            parsed_count=len(transactions),
            published_count=published,
            sample_ids=[t.id_stone for t in transactions[:5]],
        )

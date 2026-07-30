from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from stone_extracao.domain.pix.models import EventoFilaPix
from stone_extracao.domain.pix.ports import PixConciliationPort, PixMessagePublisherPort, PixParserPort
from stone_extracao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SolicitarPixResultado:
    reference_date: str
    status: str
    source: str
    message: str
    published_from_body: int = 0


class SolicitarExtratoPix:
    """Passo 1: solicita geração do extrato PIX na Stone."""

    def __init__(
        self,
        pix_client: PixConciliationPort,
        parser: PixParserPort | None = None,
        publisher: PixMessagePublisherPort | None = None,
    ) -> None:
        self.pix_client = pix_client
        self.parser = parser
        self.publisher = publisher

    async def execute(self, reference_date: str) -> SolicitarPixResultado:
        response = await self.pix_client.request_extract(reference_date)
        published = 0

        # Se a API já devolveu o arquivo no body (sample / alguns ambientes), parseia e publica
        raw = response.get("raw_bytes") or b""
        looks_like_csv = bool(raw) and not str(raw[:1].decode("utf-8", errors="ignore")).startswith("{")
        if looks_like_csv and self.parser and self.publisher:
            txs = self.parser.parse(raw)
            now = datetime.now(timezone.utc)
            for tx in txs:
                await self.publisher.publish_pix(
                    EventoFilaPix(received_at=now, first_seen_at=now, attempt=1, transaction=tx)
                )
                published += 1
            logger.info(
                "PIX body parseado | date=%s | published=%s",
                reference_date,
                published,
            )

        return SolicitarPixResultado(
            reference_date=reference_date,
            status=str(response.get("status", "accepted")),
            source=str(response.get("source", "stone_api")),
            message=str(response.get("message", "")),
            published_from_body=published,
        )

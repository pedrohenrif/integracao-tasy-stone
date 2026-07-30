from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from stone_extracao.domain.pix.models import EventoFilaPix
from stone_extracao.domain.pix.ports import PixMessagePublisherPort, PixParserPort
from stone_extracao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class PixDownloadPort(Protocol):
    async def download_file(self, url: str) -> bytes: ...


@dataclass
class WebhookPixResultado:
    source: str
    parsed_count: int
    published_count: int
    sample_ids: list[str]
    event_type: str = "pix"
    status: str = "processed"
    reference_date: str | None = None
    download_url: str | None = None


def parse_webhook_payload(raw_body: bytes | str) -> dict[str, Any] | None:
    """
    Tenta interpretar o body como JSON da Stone.
    Retorna None se for CSV (ou outro conteúdo não-JSON).
    """
    if isinstance(raw_body, bytes):
        text = raw_body.decode("utf-8", errors="replace").strip()
    else:
        text = str(raw_body).strip()
    if not text or text[0] not in "{[":
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def extract_download_url(payload: dict[str, Any]) -> str | None:
    """Aceita downloadUrl (docs request) e url (docs notificação)."""
    for key in ("downloadUrl", "download_url", "url"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class ReceberWebhookPix:
    """
    Passo 2: recebe notificação PIX no webhook público.

    Contratos suportados:
      - {"type": "validation_notification"}  → ack rápido (cadastro Stone)
      - {"type": "pix", "downloadUrl"|"url": "..."} → baixa CSV, parseia, publica
      - body CSV cru (legado / homolog manual)
    """

    def __init__(
        self,
        parser: PixParserPort,
        publisher: PixMessagePublisherPort,
        downloader: PixDownloadPort | None = None,
    ) -> None:
        self.parser = parser
        self.publisher = publisher
        self.downloader = downloader

    async def execute(
        self,
        raw_body: bytes | str,
        *,
        source: str = "webhook",
        terminals: set[str] | None = None,
        limit: int | None = None,
    ) -> WebhookPixResultado:
        logger.info(
            "Recebido | pix | fonte=%s | bytes=%s",
            source,
            len(raw_body) if isinstance(raw_body, (bytes, str)) else 0,
        )

        payload = parse_webhook_payload(raw_body)
        if payload is not None:
            event_type = str(payload.get("type") or "").strip().lower()
            if event_type == "validation_notification":
                logger.info("Webhook PIX | validation_notification ack")
                return WebhookPixResultado(
                    source=source,
                    parsed_count=0,
                    published_count=0,
                    sample_ids=[],
                    event_type="validation_notification",
                    status="ok",
                )

            download_url = extract_download_url(payload)
            if download_url:
                if self.downloader is None:
                    raise RuntimeError("Downloader PIX não configurado para downloadUrl")
                logger.info(
                    "Webhook PIX | type=%s | baixando CSV | ref=%s",
                    event_type or "pix",
                    payload.get("referenceDate") or payload.get("reference_date"),
                )
                csv_bytes = await self.downloader.download_file(download_url)
                result = await self._publish_csv(
                    csv_bytes,
                    source=f"{source}:download",
                    terminals=terminals,
                    limit=limit,
                )
                result.event_type = event_type or "pix"
                result.reference_date = (
                    str(payload.get("referenceDate") or payload.get("reference_date") or "")
                    or None
                )
                result.download_url = download_url
                return result

            if event_type == "pix":
                raise ValueError(
                    "Notificação PIX sem downloadUrl/url — payload incompleto da Stone"
                )

        return await self._publish_csv(
            raw_body,
            source=source,
            terminals=terminals,
            limit=limit,
        )

    async def _publish_csv(
        self,
        raw_body: bytes | str,
        *,
        source: str,
        terminals: set[str] | None,
        limit: int | None,
    ) -> WebhookPixResultado:
        transactions = self.parser.parse(raw_body)
        parsed_total = len(transactions)

        if terminals:
            wanted = {t.strip() for t in terminals if t and t.strip()}
            transactions = [t for t in transactions if t.nr_serie_maquininha in wanted]
        if limit is not None and limit >= 0:
            transactions = transactions[:limit]

        logger.info(
            "Parseado | pix | total=%s | apos_filtro=%s | terminals=%s | limit=%s",
            parsed_total,
            len(transactions),
            sorted(terminals) if terminals else None,
            limit,
        )

        now = datetime.now(timezone.utc)
        published = 0
        for tx in transactions:
            evento = EventoFilaPix(
                received_at=now,
                first_seen_at=now,
                attempt=1,
                transaction=tx,
            )
            await self.publisher.publish_pix(evento)
            published += 1

        return WebhookPixResultado(
            source=source,
            parsed_count=parsed_total,
            published_count=published,
            sample_ids=[t.id_stone for t in transactions[:5]],
            event_type="pix",
            status="processed",
        )

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from stone_extracao.domain.pix.models import EventoFilaPix
from stone_extracao.domain.pix.ports import PixMessagePublisherPort, PixParserPort
from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.store.pix_backup import (
    save_pix_conferencia,
    save_pix_csv_backup,
)

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
    backup_path: str | None = None
    conferencia_path: str | None = None
    alerta: str | None = None
    skipped_serial: int = 0
    parse_stats: dict[str, Any] = field(default_factory=dict)
    conferencia: dict[str, Any] = field(default_factory=dict)


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
        reference_date: str | None = None,
    ) -> WebhookPixResultado:
        body_len = len(raw_body) if isinstance(raw_body, (bytes, str)) else 0
        logger.info("Recebido | pix | fonte=%s | bytes=%s", source, body_len)

        payload = parse_webhook_payload(raw_body)
        if payload is not None:
            event_type = str(payload.get("type") or "").strip().lower()
            keys = sorted(str(k) for k in payload.keys())
            logger.info(
                "Webhook PIX | json | type=%s | keys=%s",
                event_type or "-",
                ",".join(keys[:30]),
            )
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
                ref = payload.get("referenceDate") or payload.get("reference_date")
                logger.info(
                    "Webhook PIX | type=%s | baixando CSV | ref=%s | url=%s",
                    event_type or "pix",
                    ref,
                    download_url[:160],
                )
                csv_bytes = await self.downloader.download_file(download_url)
                result = await self._publish_csv(
                    csv_bytes,
                    source=f"{source}:download",
                    terminals=terminals,
                    limit=limit,
                    reference_date=str(ref or "").strip() or (reference_date or None),
                )
                result.event_type = event_type or "pix"
                result.download_url = download_url
                logger.info(
                    "Webhook PIX | publicado | ref=%s | parsed=%s | published=%s | samples=%s",
                    result.reference_date,
                    result.parsed_count,
                    result.published_count,
                    result.sample_ids,
                )
                return result

            if event_type == "pix":
                logger.error(
                    "Webhook PIX | type=pix sem downloadUrl/url | keys=%s | payload=%s",
                    keys,
                    str(payload)[:400],
                )
                raise ValueError(
                    "Notificação PIX sem downloadUrl/url — payload incompleto da Stone"
                )

        return await self._publish_csv(
            raw_body,
            source=source,
            terminals=terminals,
            limit=limit,
            reference_date=reference_date,
        )

    def _parse_csv(self, raw_body: bytes | str):
        parse_stats = getattr(self.parser, "parse_with_stats", None)
        if callable(parse_stats):
            parsed = parse_stats(raw_body)
            return parsed.transactions, parsed.stats.as_dict(), parsed.stats.summary()
        txs = self.parser.parse(raw_body)
        return txs, {"accepted": len(txs)}, f"aceitas={len(txs)}"

    async def _publish_csv(
        self,
        raw_body: bytes | str,
        *,
        source: str,
        terminals: set[str] | None,
        limit: int | None,
        reference_date: str | None = None,
    ) -> WebhookPixResultado:
        transactions, parse_stats, parse_summary = self._parse_csv(raw_body)
        parsed_total = len(transactions)
        dates = [t.reference_date for t in transactions if t.reference_date]
        ref = (reference_date or "").strip() or (
            Counter(dates).most_common(1)[0][0] if dates else datetime.now().strftime("%Y-%m-%d")
        )

        backup_path = None
        try:
            saved = save_pix_csv_backup(raw_body, reference_date=ref, source=source)
            if saved is not None:
                backup_path = str(saved.path)
        except Exception:
            logger.exception("Backup CSV PIX falhou | date=%s | source=%s", ref, source)

        skipped_serial: list[dict[str, str]] = []
        if terminals:
            wanted = {t.strip() for t in terminals if t and t.strip()}
            kept = []
            for t in transactions:
                if t.nr_serie_maquininha in wanted:
                    kept.append(t)
                else:
                    skipped_serial.append(
                        {
                            "id_stone": t.id_stone,
                            "serial": t.nr_serie_maquininha,
                            "valor": str(t.vl_transacao),
                        }
                    )
            transactions = kept
        if limit is not None and limit >= 0:
            transactions = transactions[:limit]

        logger.info(
            "Parseado | pix | %s | apos_filtro=%s | fora_piloto=%s | terminals=%s | limit=%s | backup=%s",
            parse_summary,
            len(transactions),
            len(skipped_serial),
            sorted(terminals) if terminals else None,
            limit,
            backup_path or "-",
        )
        if skipped_serial:
            logger.warning(
                "PIX fora do piloto (não publicado) | date=%s | qtd=%s | amostras=%s",
                ref,
                len(skipped_serial),
                skipped_serial[:10],
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

        gaps_inesperados = (
            int(parse_stats.get("skipped_no_id") or 0)
            + int(parse_stats.get("skipped_no_amount") or 0)
            + int(parse_stats.get("skipped_no_date") or 0)
        )
        alerta = None
        if skipped_serial:
            alerta = (
                f"{len(skipped_serial)} PIX paid fora do PUBLICAR_SOMENTE_SERIAIS "
                "(não publicados — conferir serial no piloto)"
            )
        elif gaps_inesperados:
            alerta = (
                f"{gaps_inesperados} linhas paid sem id/valor/data "
                "(parser descartou — conferir CSV na VM)"
            )
        conferencia = {
            "at": now.astimezone().isoformat(timespec="seconds"),
            "source": source,
            "reference_date": ref,
            "backup_path": backup_path,
            "parse": parse_stats,
            "parse_summary": parse_summary,
            "paid_parseados": parsed_total,
            "publicados": published,
            "fora_piloto": len(skipped_serial),
            "fora_piloto_amostras": skipped_serial[:30],
            "ids_publicados": [t.id_stone for t in transactions],
            "ok": not skipped_serial and gaps_inesperados == 0,
            "alerta": alerta,
        }
        try:
            conf_path = save_pix_conferencia(reference_date=ref, payload=conferencia)
            if conf_path is not None:
                conferencia["conferencia_path"] = str(conf_path)
        except Exception:
            logger.exception("Conferência PIX falhou | date=%s", ref)

        if conferencia.get("alerta"):
            logger.warning(
                "Conferência PIX | date=%s | publicados=%s/%s | %s",
                ref,
                published,
                parsed_total,
                conferencia["alerta"],
            )
        else:
            logger.info(
                "Conferência PIX | date=%s | publicados=%s/%s | backup=%s",
                ref,
                published,
                parsed_total,
                backup_path or "-",
            )

        return WebhookPixResultado(
            source=source,
            parsed_count=parsed_total,
            published_count=published,
            sample_ids=[t.id_stone for t in transactions[:5]],
            event_type="pix",
            status="processed",
            reference_date=ref,
            backup_path=backup_path,
            conferencia_path=str(conferencia.get("conferencia_path") or "") or None,
            alerta=alerta,
            skipped_serial=len(skipped_serial),
            parse_stats=parse_stats,
            conferencia=conferencia,
        )

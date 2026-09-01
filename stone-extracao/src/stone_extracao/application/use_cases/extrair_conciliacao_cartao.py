from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from stone_extracao.domain.cartao.models import EventoFilaCartao, TransacaoCartao
from stone_extracao.domain.cartao.ports import (
    CartaoParserPort,
    ConciliationFilePort,
    MessagePublisherPort,
)
from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.parsers.cartao_totais import analyze_cartao_totais
from stone_extracao.infrastructure.store.xml_backup import save_cartao_xml_backup

logger = get_logger(__name__)


@dataclass
class ExtracaoResultado:
    reference_date: str
    source: str
    parsed_count: int
    published_count: int
    sample_ids: list[str]
    transactions: list[TransacaoCartao]
    totais_avisos: list[str] | None = None
    message: str | None = None
    raw_bytes: int | None = None
    parse_stats: dict[str, Any] = field(default_factory=dict)
    xml_backup_path: str | None = None


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

    async def execute(
        self,
        reference_date: str,
        *,
        terminals: set[str] | None = None,
    ) -> ExtracaoResultado:
        raw = await self.stone_client.fetch(reference_date)
        raw_bytes = len(raw)
        logger.info("Recebido | cartao | date=%s | bytes=%s", reference_date, raw_bytes)

        backup_path: str | None = None
        parse_stats: dict[str, Any] = {}
        parse_with_stats = getattr(self.parser, "parse_with_stats", None)
        if callable(parse_with_stats):
            parsed = parse_with_stats(raw)
            transactions = parsed.transactions
            stats = parsed.stats
            parse_stats = {
                "has_financial_section": stats.has_financial_section,
                "transactions_total": stats.transactions_total,
                "accepted": stats.accepted,
                "skipped_no_capture": stats.skipped_no_capture,
                "skipped_no_id": stats.skipped_no_id,
                "skipped_no_amount": stats.skipped_no_amount,
                "skipped_no_date": stats.skipped_no_date,
                "international_true": stats.international_true,
                "international_false": stats.international_false,
                "stone_code": stats.stone_code,
                "reference_date": stats.reference_date,
                "layout_version": stats.layout_version,
                "root_sections": dict(stats.root_sections),
                "summary": stats.summary(),
            }
            logger.info("Parseado | cartao | date=%s | %s", reference_date, stats.summary())
        else:
            transactions = self.parser.parse(raw)
            logger.info(
                "Parseado | cartao | date=%s | count=%s",
                reference_date,
                len(transactions),
            )

        if terminals:
            wanted = {t.strip() for t in terminals if t and str(t).strip()}
            before = len(transactions)
            transactions = [
                t for t in transactions if (t.nr_serie_maquininha or "").strip() in wanted
            ]
            logger.info(
                "Filtro serial | cartao | date=%s | antes=%s | depois=%s | terminals=%s",
                reference_date,
                before,
                len(transactions),
                sorted(wanted),
            )
            parse_stats["filter_terminals"] = sorted(wanted)
            parse_stats["filtered_from"] = before
            parse_stats["filtered_to"] = len(transactions)

        tag = "ok" if transactions else "vazio"
        try:
            saved = save_cartao_xml_backup(
                raw,
                reference_date=reference_date,
                tag=tag,
            )
            if saved:
                backup_path = str(saved.path)
                parse_stats["xml_backup_path"] = backup_path
        except Exception as dump_exc:
            logger.warning("Backup XML falhou | date=%s | %s", reference_date, dump_exc)

        if not transactions:
            logger.warning(
                "Nenhuma transação parseada | cartao | date=%s | bytes=%s | stats=%s | backup=%s",
                reference_date,
                raw_bytes,
                parse_stats.get("summary") or "(sem stats)",
                backup_path or "-",
            )

        totais = analyze_cartao_totais(raw, transactions)
        for aviso in totais.avisos:
            logger.warning("Totais cartão | date=%s | %s", reference_date, aviso)
        if totais.tem_divergencia:
            logger.error(
                "Divergência arredondamento | date=%s | soma=%s | arquivo=%s | delta=%s",
                reference_date,
                totais.soma_transacoes,
                totais.total_arquivo,
                totais.divergencia,
            )
        else:
            logger.info(
                "Totais cartão | date=%s | soma_txs=%s | grupos=%s",
                reference_date,
                totais.soma_transacoes,
                len(totais.por_bandeira_tipo),
            )

        now = datetime.now(timezone.utc)
        published = 0
        # Ordena por serial para o consumer FECHAR um recebimento antes de abrir o da
        # próxima maquininha (Tasy: 1 lote aberto por caixa).
        for tx in sorted(
            transactions,
            key=lambda t: (t.nr_serie_maquininha or "", t.id_stone or ""),
        ):
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
        message = None
        if not transactions:
            detail = parse_stats.get("summary") or "sem FinancialTransactions/Captures"
            skipped_cap = parse_stats.get("skipped_no_capture")
            total_xml = parse_stats.get("transactions_total")
            if total_xml and skipped_cap and skipped_cap == total_xml:
                message = (
                    f"Arquivo Stone OK ({raw_bytes} bytes) com {total_xml} transação(ões) no XML, "
                    f"mas nenhuma com Captures>=1 (só liquidação/cancelamento/etc.). "
                    f"Integração Tasy usa apenas capturas. | {detail}"
                )
            else:
                message = (
                    f"Stone retornou arquivo sem transações parseáveis "
                    f"(date={reference_date}, bytes={raw_bytes}). {detail}"
                )
            if backup_path:
                message = f"{message} | backup={backup_path}"
        return ExtracaoResultado(
            reference_date=reference_date,
            source=source,
            parsed_count=len(transactions),
            published_count=published,
            sample_ids=[t.id_stone for t in transactions[:5]],
            transactions=transactions,
            totais_avisos=list(totais.avisos),
            message=message,
            raw_bytes=raw_bytes,
            parse_stats=parse_stats,
            xml_backup_path=backup_path,
        )

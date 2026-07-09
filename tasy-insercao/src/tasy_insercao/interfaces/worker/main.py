from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime, timezone

from aio_pika.abc import AbstractIncomingMessage

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import EventoFilaCartao, StatusIntegracao
from tasy_insercao.infrastructure.config.logging import get_logger, setup_logging
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.messaging.rabbit import (
    RetryPublisher,
    close_rabbitmq,
    connect_rabbitmq,
    declare_topology,
    delay_for_attempt,
)
from tasy_insercao.infrastructure.persistence.oracle import OracleDB, TasyOracleRepository
from tasy_insercao.infrastructure.persistence.postgres import (
    PostgresDB,
    StagingPostgresRepository,
)

logger = get_logger(__name__)

_pg_db: PostgresDB | None = None
_ora_db: OracleDB | None = None
_use_case: IntegrarTransacaoCartao | None = None
_retry_publisher: RetryPublisher | None = None


def _build_use_case() -> IntegrarTransacaoCartao:
    global _pg_db, _ora_db, _use_case
    if _use_case is None:
        _pg_db = PostgresDB()
        _ora_db = OracleDB()
        _use_case = IntegrarTransacaoCartao(
            staging=StagingPostgresRepository(_pg_db),
            tasy=TasyOracleRepository(_ora_db),
        )
    return _use_case


def _reset_connections() -> None:
    global _use_case
    if _pg_db:
        _pg_db.reset()
    if _ora_db:
        _ora_db.reset()
    _use_case = None


async def handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        raw = message.body.decode("utf-8")
        data = json.loads(raw)
        evento = EventoFilaCartao.model_validate(data)
        tx = evento.transaction

        if evento.first_seen_at is None:
            evento.first_seen_at = evento.received_at

        logger.info(
            "Recebido fila | id_stone=%s | attempt=%s/%s | valor=%s",
            tx.id_stone,
            evento.attempt,
            settings.RETRY_MAX_ATTEMPTS,
            tx.vl_transacao,
        )

        use_case = _build_use_case()
        try:
            resultado = await asyncio.to_thread(use_case.execute, tx)
        except Exception as exc:
            # Falha inesperada (ex.: conexão caiu no meio) → trata como retryable
            logger.exception("Erro inesperado | id_stone=%s | %s", tx.id_stone, exc)
            _reset_connections()
            await _schedule_retry_or_dlq(evento, str(exc), retryable=True)
            return

        if resultado.status == StatusIntegracao.INTEGRADO:
            logger.info("Inserido | id_stone=%s | %s", tx.id_stone, resultado.mensagem)
            return

        if resultado.retryable and evento.attempt < settings.RETRY_MAX_ATTEMPTS:
            _reset_connections()
            await _schedule_retry_or_dlq(evento, resultado.mensagem, retryable=True)
            return

        # Erro definitivo OU esgotou tentativas → DLQ (não descarta o payload)
        await _schedule_retry_or_dlq(evento, resultado.mensagem, retryable=False)


async def _schedule_retry_or_dlq(
    evento: EventoFilaCartao,
    error: str,
    *,
    retryable: bool,
) -> None:
    assert _retry_publisher is not None
    evento.last_error = error[:500]

    if retryable and evento.attempt < settings.RETRY_MAX_ATTEMPTS:
        next_attempt = evento.attempt + 1
        delay = delay_for_attempt(evento.attempt)
        retry_evento = evento.model_copy(
            update={
                "attempt": next_attempt,
                "received_at": datetime.now(timezone.utc),
                "last_error": error[:500],
            }
        )
        await _retry_publisher.publish_retry(retry_evento, delay)
        return

    await _retry_publisher.publish_dlq(evento)


async def run_worker() -> None:
    global _retry_publisher
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queues = await declare_topology(channel)
    _retry_publisher = RetryPublisher(channel)

    logger.info(
        "Consumer iniciado | queue=%s | retry=%s | dlq=%s | max_attempts=%s",
        settings.RABBITMQ_QUEUE_CARTAO,
        settings.RABBITMQ_QUEUE_RETRY,
        settings.RABBITMQ_QUEUE_DLQ,
        settings.RETRY_MAX_ATTEMPTS,
    )
    await queues["main"].consume(handle_message)

    stop_event = asyncio.Event()

    def _stop(*_args) -> None:
        stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop)
            except NotImplementedError:
                signal.signal(sig, lambda *_: _stop())
    except Exception:
        pass

    await stop_event.wait()
    if _ora_db:
        _ora_db.close()
    if _pg_db:
        _pg_db.close()
    await close_rabbitmq(connection)


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Consumer interrompido")


if __name__ == "__main__":
    main()

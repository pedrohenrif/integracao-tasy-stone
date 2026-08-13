from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime, timezone
from typing import Any

from aio_pika.abc import AbstractIncomingMessage

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.application.use_cases.integrar_transacao_pix import IntegrarTransacaoPix
from tasy_insercao.domain.integracao.models import (
    EventoFilaCartao,
    EventoFilaPix,
    StatusIntegracao,
)
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
_use_case_cartao: IntegrarTransacaoCartao | None = None
_use_case_pix: IntegrarTransacaoPix | None = None
_retry_publisher: RetryPublisher | None = None


def _build_services() -> tuple[IntegrarTransacaoCartao, IntegrarTransacaoPix]:
    global _pg_db, _ora_db, _use_case_cartao, _use_case_pix
    if _use_case_cartao is None or _use_case_pix is None:
        _pg_db = PostgresDB()
        _ora_db = OracleDB()
        staging = StagingPostgresRepository(_pg_db)
        tasy = TasyOracleRepository(_ora_db)
        _use_case_cartao = IntegrarTransacaoCartao(staging, tasy)
        _use_case_pix = IntegrarTransacaoPix(staging, tasy)
    return _use_case_cartao, _use_case_pix


def _reset_connections() -> None:
    global _use_case_cartao, _use_case_pix
    if _pg_db:
        _pg_db.reset()
    if _ora_db:
        _ora_db.reset()
    _use_case_cartao = None
    _use_case_pix = None


async def _schedule_retry_or_dlq(evento: Any, error: str, *, fluxo: str, retryable: bool) -> None:
    assert _retry_publisher is not None
    evento.last_error = error[:500]

    if retryable and evento.attempt < settings.RETRY_MAX_ATTEMPTS:
        delay = delay_for_attempt(evento.attempt)
        retry_evento = evento.model_copy(
            update={
                "attempt": evento.attempt + 1,
                "received_at": datetime.now(timezone.utc),
                "last_error": error[:500],
            }
        )
        await _retry_publisher.publish_retry(retry_evento, delay, fluxo=fluxo)
        return

    await _retry_publisher.publish_dlq(evento, fluxo=fluxo)


async def handle_cartao(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        evento = EventoFilaCartao.model_validate(json.loads(message.body.decode("utf-8")))
        if evento.first_seen_at is None:
            evento.first_seen_at = evento.received_at

        logger.info(
            "Recebido fila | cartao | id_stone=%s | attempt=%s/%s",
            evento.transaction.id_stone,
            evento.attempt,
            settings.RETRY_MAX_ATTEMPTS,
        )

        cartao_uc, _ = _build_services()
        try:
            resultado = await asyncio.to_thread(cartao_uc.execute, evento.transaction)
        except Exception as exc:
            logger.exception("Erro inesperado | cartao | %s", exc)
            _reset_connections()
            await _schedule_retry_or_dlq(evento, str(exc), fluxo="cartao", retryable=True)
            return

        if resultado.status == StatusIntegracao.INTEGRADO:
            logger.info("Inserido | cartao | id_stone=%s | %s", resultado.id_stone, resultado.mensagem)
            return

        if resultado.status == StatusIntegracao.SEM_TESOURARIA:
            logger.info(
                "Inserido sem tesouraria | cartao | id_stone=%s | %s",
                resultado.id_stone,
                resultado.mensagem,
            )
            return

        if resultado.status == StatusIntegracao.CONFIRMACAO_PENDENTE:
            logger.warning(
                "Confirmação pendente | cartao | id_stone=%s | %s",
                resultado.id_stone,
                resultado.mensagem,
            )
            return

        if resultado.retryable and evento.attempt < settings.RETRY_MAX_ATTEMPTS:
            _reset_connections()
            await _schedule_retry_or_dlq(evento, resultado.mensagem, fluxo="cartao", retryable=True)
            return

        await _schedule_retry_or_dlq(evento, resultado.mensagem, fluxo="cartao", retryable=False)


async def handle_pix(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        evento = EventoFilaPix.model_validate(json.loads(message.body.decode("utf-8")))
        if evento.first_seen_at is None:
            evento.first_seen_at = evento.received_at

        logger.info(
            "Recebido fila | pix | id_stone=%s | e2e=%s | attempt=%s/%s",
            evento.transaction.id_stone,
            evento.transaction.e2e_id,
            evento.attempt,
            settings.RETRY_MAX_ATTEMPTS,
        )

        _, pix_uc = _build_services()
        try:
            resultado = await asyncio.to_thread(pix_uc.execute, evento.transaction)
        except Exception as exc:
            logger.exception("Erro inesperado | pix | %s", exc)
            _reset_connections()
            await _schedule_retry_or_dlq(evento, str(exc), fluxo="pix", retryable=True)
            return

        if resultado.status == StatusIntegracao.INTEGRADO:
            logger.info("Inserido | pix | id_stone=%s | %s", resultado.id_stone, resultado.mensagem)
            return

        if resultado.status == StatusIntegracao.SEM_TESOURARIA:
            logger.info(
                "Inserido sem tesouraria | pix | id_stone=%s | %s",
                resultado.id_stone,
                resultado.mensagem,
            )
            return

        if resultado.status == StatusIntegracao.CONFIRMACAO_PENDENTE:
            logger.warning(
                "Confirmação pendente | pix | id_stone=%s | %s",
                resultado.id_stone,
                resultado.mensagem,
            )
            return

        if resultado.retryable and evento.attempt < settings.RETRY_MAX_ATTEMPTS:
            _reset_connections()
            await _schedule_retry_or_dlq(evento, resultado.mensagem, fluxo="pix", retryable=True)
            return

        await _schedule_retry_or_dlq(evento, resultado.mensagem, fluxo="pix", retryable=False)


async def run_worker() -> None:
    global _retry_publisher
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queues = await declare_topology(channel)
    _retry_publisher = RetryPublisher(channel)

    logger.info(
        "Consumer iniciado | cartao=%s | pix=%s | max_attempts=%s",
        settings.RABBITMQ_QUEUE_CARTAO,
        settings.RABBITMQ_QUEUE_PIX,
        settings.RETRY_MAX_ATTEMPTS,
    )
    await queues["cartao"]["main"].consume(handle_cartao)
    await queues["pix"]["main"].consume(handle_pix)

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

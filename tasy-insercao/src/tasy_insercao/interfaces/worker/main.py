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
from tasy_insercao.infrastructure.messaging.fechar_quando_fila_vazia import (
    fechar_se_fila_cartao_vazia,
)
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
_consumer_channel: Any = None


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


async def _run_integracao(fluxo: str, execute_fn, transaction) -> Any:
    """Executa use case em thread com timeout (não trava prefetch=1)."""
    timeout = max(30, int(settings.CONSUMER_HANDLER_TIMEOUT_SECONDS or 180))
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(execute_fn, transaction),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        _reset_connections()
        raise TimeoutError(
            f"Timeout {timeout}s no handler {fluxo} (Oracle/PG). "
            "Conexões resetadas; mensagem vai para retry."
        ) from None


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
            resultado = await _run_integracao("cartao", cartao_uc.execute, evento.transaction)
        except Exception as exc:
            logger.exception("Erro inesperado | cartao | %s", exc)
            _reset_connections()
            await _schedule_retry_or_dlq(evento, str(exc), fluxo="cartao", retryable=True)
            return

        if resultado.status == StatusIntegracao.INTEGRADO:
            logger.info("Inserido | cartao | id_stone=%s | %s", resultado.id_stone, resultado.mensagem)
            if resultado.nr_seq_caixa_receb and _consumer_channel is not None:
                dt_saldo = evento.transaction.dt_movimentacao
                dt_str = (
                    dt_saldo.date().isoformat()
                    if hasattr(dt_saldo, "date")
                    else str(dt_saldo)[:10]
                )
                cartao_uc, _ = _build_services()
                confirmar = getattr(cartao_uc.tasy, "confirmar_caixa_receb_stone", None)
                if confirmar is not None:
                    await fechar_se_fila_cartao_vazia(
                        _consumer_channel,
                        nr_seq_caixa_rec=int(resultado.nr_seq_caixa_rec),
                        dt_recebimento=dt_str,
                        confirmar_fn=confirmar,
                        serial=evento.transaction.nr_serie_maquininha,
                    )
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
            resultado = await _run_integracao("pix", pix_uc.execute, evento.transaction)
        except Exception as exc:
            logger.exception("Erro inesperado | pix | %s", exc)
            _reset_connections()
            await _schedule_retry_or_dlq(evento, str(exc), fluxo="pix", retryable=True)
            return

        if resultado.status == StatusIntegracao.INTEGRADO:
            logger.info("Inserido | pix | id_stone=%s | %s", resultado.id_stone, resultado.mensagem)
            # PIX: FECHAR so na troca de serial (ensure). Nao usa "fila cartao vazia".
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


async def _heartbeat_loop(stop_event: asyncio.Event) -> None:
    interval = max(60, int(settings.CONSUMER_HEARTBEAT_SECONDS or 300))
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            logger.info(
                "Consumer heartbeat | a escuta | cartao=%s | pix=%s",
                settings.RABBITMQ_QUEUE_CARTAO,
                settings.RABBITMQ_QUEUE_PIX,
            )


async def _run_session(stop_event: asyncio.Event) -> None:
    """Uma sessão Rabbit: connect -> consume -> espera stop ou queda da conexão."""
    global _retry_publisher, _consumer_channel
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queues = await declare_topology(channel)
    _retry_publisher = RetryPublisher(channel)
    _consumer_channel = channel

    logger.info(
        "Consumer iniciado | cartao=%s | pix=%s | max_attempts=%s | handler_timeout=%ss",
        settings.RABBITMQ_QUEUE_CARTAO,
        settings.RABBITMQ_QUEUE_PIX,
        settings.RETRY_MAX_ATTEMPTS,
        settings.CONSUMER_HANDLER_TIMEOUT_SECONDS,
    )
    await queues["cartao"]["main"].consume(handle_cartao)
    await queues["pix"]["main"].consume(handle_pix)

    conn_closed = asyncio.Event()

    async def _watch_connection() -> None:
        while not stop_event.is_set():
            if connection.is_closed:
                conn_closed.set()
                return
            await asyncio.sleep(5)

    watch = asyncio.create_task(_watch_connection())
    heartbeat = asyncio.create_task(_heartbeat_loop(stop_event))
    try:
        stop_task = asyncio.create_task(stop_event.wait())
        closed_task = asyncio.create_task(conn_closed.wait())
        done, pending = await asyncio.wait(
            {stop_task, closed_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if conn_closed.is_set() and not stop_event.is_set():
            logger.warning("Consumer | conexão RabbitMQ fechou; vai reconectar")
    finally:
        watch.cancel()
        heartbeat.cancel()
        for task in (watch, heartbeat):
            try:
                await task
            except asyncio.CancelledError:
                pass
        if _ora_db:
            try:
                _ora_db.close()
            except Exception:
                pass
        if _pg_db:
            try:
                _pg_db.close()
            except Exception:
                pass
        _reset_connections()
        _consumer_channel = None
        await close_rabbitmq(connection)


async def run_worker() -> None:
    setup_logging()
    stop_event = asyncio.Event()

    def _stop(*_args: Any) -> None:
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

    delay = max(1, int(settings.CONSUMER_RECONNECT_DELAY_SECONDS or 5))
    while not stop_event.is_set():
        try:
            await _run_session(stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Consumer | sessão falhou; reconecta em %ss",
                delay,
            )
            _reset_connections()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Consumer interrompido")


if __name__ == "__main__":
    main()

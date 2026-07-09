from __future__ import annotations

import asyncio
import json
import signal

from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.oracle import OracleDB
from app.core.postgres import PostgresDB
from app.core.rabbit import close_rabbitmq, connect_rabbitmq, declare_cartao_queue
from app.schemas.cartao import EventoFilaCartao
from app.services.tasy_service import STATUS_ERRO, STATUS_INTEGRADO, TasyService

logger = get_logger(__name__)

_pg: PostgresDB | None = None
_oracle: OracleDB | None = None
_tasy: TasyService | None = None


def _get_tasy() -> TasyService:
    global _pg, _oracle, _tasy
    if _tasy is None:
        _pg = PostgresDB()
        _oracle = OracleDB()
        _tasy = TasyService(_pg, _oracle)
    return _tasy


async def handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        raw = message.body.decode("utf-8")
        data = json.loads(raw)
        evento = EventoFilaCartao.model_validate(data)
        tx = evento.transaction

        logger.info(
            "Recebido fila | cartao | id_stone=%s | terminal=%s | tipo=%s | valor=%s",
            tx.id_stone,
            tx.nr_serie_maquininha,
            tx.cd_tipo_transacao.value,
            tx.vl_transacao,
        )

        tasy = _get_tasy()
        # Oracle/PG são sync — roda em thread para não bloquear o loop do aio-pika
        resultado = await asyncio.to_thread(tasy.processar_transacao_cartao, tx)

        if resultado.status == STATUS_INTEGRADO:
            logger.info(
                "Inserido | cartao | id_stone=%s | status=%s | %s",
                resultado.id_stone,
                resultado.status,
                resultado.mensagem,
            )
        elif resultado.status == STATUS_ERRO:
            logger.error(
                "Falha | cartao | id_stone=%s | status=%s | %s",
                resultado.id_stone,
                resultado.status,
                resultado.mensagem,
            )
        else:
            logger.warning(
                "Consumido | cartao | id_stone=%s | status=%s | %s",
                resultado.id_stone,
                resultado.status,
                resultado.mensagem,
            )


async def run_worker() -> None:
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await declare_cartao_queue(channel, settings.RABBITMQ_QUEUE_CARTAO)

    logger.info(
        "Consumer iniciado | queue=%s | modo=Tasy (Caixa→Dia→Transação)",
        settings.RABBITMQ_QUEUE_CARTAO,
    )
    await queue.consume(handle_message)

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

    if _oracle:
        _oracle.close()
    if _pg:
        _pg.close()
    await close_rabbitmq(connection)


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Consumer interrompido")


if __name__ == "__main__":
    main()

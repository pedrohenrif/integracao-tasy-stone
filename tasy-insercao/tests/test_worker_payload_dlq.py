import asyncio
import json
from unittest.mock import AsyncMock

from tasy_insercao.domain.integracao.models import EventoFilaCartao
from tasy_insercao.interfaces.worker import main as worker


class FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.requeued: bool | None = None

    def process(self, requeue: bool = False):
        inner = self

        class _Ctx:
            async def __aenter__(self):
                return inner

            async def __aexit__(self, exc_type, exc, tb):
                if exc_type is None:
                    inner.acked = True
                    return False
                inner.requeued = requeue
                return False

        return _Ctx()


def test_peek_id_stone_do_envelope():
    body = json.dumps({"transaction": {"id_stone": "39562372188930"}}).encode()
    assert worker.peek_id_stone(body) == "39562372188930"


def test_peek_id_stone_json_quebrado():
    assert worker.peek_id_stone(b"{nao-json") is None


def test_parse_evento_cartao_invalido():
    evento, err = worker.parse_evento(EventoFilaCartao, b"{}")
    assert evento is None
    assert err is not None


def test_payload_invalido_cartao_vai_para_dlq_e_ack():
    """Antes: process(requeue=False) descartava sem DLQ e sem id no log."""
    msg = FakeMessage(b"{nao-json")
    pub = AsyncMock()
    worker._retry_publisher = pub
    try:
        asyncio.get_event_loop().run_until_complete(worker.handle_cartao(msg))
    finally:
        worker._retry_publisher = None
    pub.publish_dlq_raw.assert_awaited_once()
    kwargs = pub.publish_dlq_raw.await_args
    assert kwargs.kwargs["fluxo"] == "cartao"
    assert msg.acked is True
    assert msg.requeued is None


def test_payload_invalido_pix_vai_para_dlq_e_ack():
    msg = FakeMessage(b"[]")
    pub = AsyncMock()
    worker._retry_publisher = pub
    try:
        asyncio.get_event_loop().run_until_complete(worker.handle_pix(msg))
    finally:
        worker._retry_publisher = None
    pub.publish_dlq_raw.assert_awaited_once()
    assert pub.publish_dlq_raw.await_args.kwargs["fluxo"] == "pix"
    assert msg.acked is True

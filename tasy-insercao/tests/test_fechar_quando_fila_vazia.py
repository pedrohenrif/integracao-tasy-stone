import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tasy_insercao.infrastructure.messaging import fechar_quando_fila_vazia as fq


def test_nao_fecha_se_cartao_tem_msgs(monkeypatch):
    monkeypatch.setattr(fq.settings, "FECHAR_ULTIMO_RECEB_ENABLED", True)
    channel = MagicMock()
    confirmar = MagicMock()

    async def _ready(ch, name):
        if "pix" in name:
            return 0
        return 3

    async def _run() -> None:
        with patch.object(fq, "_mensagens_prontas", new=AsyncMock(side_effect=_ready)):
            ok = await fq.fechar_se_filas_vazias(
                channel,
                nr_seq_caixa_rec=10,
                dt_recebimento="2026-08-25",
                confirmar_fn=confirmar,
                serial="A",
            )
        assert ok is False

    asyncio.run(_run())
    confirmar.assert_not_called()


def test_nao_fecha_se_pix_tem_msgs(monkeypatch):
    monkeypatch.setattr(fq.settings, "FECHAR_ULTIMO_RECEB_ENABLED", True)
    channel = MagicMock()
    confirmar = MagicMock()

    async def _ready(ch, name):
        if "pix" in name:
            return 2
        return 0

    async def _run() -> None:
        with patch.object(fq, "_mensagens_prontas", new=AsyncMock(side_effect=_ready)):
            ok = await fq.fechar_se_filas_vazias(
                channel,
                nr_seq_caixa_rec=10,
                dt_recebimento="2026-08-25",
                confirmar_fn=confirmar,
            )
        assert ok is False

    asyncio.run(_run())
    confirmar.assert_not_called()


def test_fecha_quando_ambas_filas_vazias(monkeypatch):
    monkeypatch.setattr(fq.settings, "FECHAR_ULTIMO_RECEB_ENABLED", True)
    channel = MagicMock()
    confirmar = MagicMock(return_value=0.0)

    async def _run() -> None:
        with patch.object(fq, "_mensagens_prontas", new=AsyncMock(return_value=0)):
            ok = await fq.fechar_se_filas_vazias(
                channel,
                nr_seq_caixa_rec=10,
                dt_recebimento="2026-08-25",
                confirmar_fn=confirmar,
                serial="A",
            )
        assert ok is True

    asyncio.run(_run())
    confirmar.assert_called_once_with(10, "2026-08-25")

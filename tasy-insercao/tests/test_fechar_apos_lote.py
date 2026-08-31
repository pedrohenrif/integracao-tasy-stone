import asyncio
from unittest.mock import MagicMock

from tasy_insercao.infrastructure.messaging import fechar_apos_lote as fal


def test_remarca_e_fecha_apos_quiet(monkeypatch):
    monkeypatch.setattr(fal.settings, "FECHAR_APOS_LOTE_ENABLED", True)
    monkeypatch.setattr(fal.settings, "FECHAR_APOS_LOTE_SECONDS", 1)

    calls: list[tuple[int, str]] = []

    def confirmar(nr: int, dt: str) -> float:
        calls.append((nr, dt))
        return 0.0

    async def _run() -> None:
        fal.schedule_fechar_apos_lote(
            nr_seq_caixa_rec=10,
            dt_recebimento="2026-08-25",
            confirmar_fn=confirmar,
            serial="A",
            fluxo="cartao",
        )
        fal.schedule_fechar_apos_lote(
            nr_seq_caixa_rec=10,
            dt_recebimento="2026-08-25",
            confirmar_fn=confirmar,
            serial="A",
            fluxo="pix",
        )
        await asyncio.sleep(1.3)

    asyncio.run(_run())
    assert calls == [(10, "2026-08-25")]


def test_cartao_e_pix_mesmo_timer(monkeypatch):
    monkeypatch.setattr(fal.settings, "FECHAR_APOS_LOTE_ENABLED", True)
    monkeypatch.setattr(fal.settings, "FECHAR_APOS_LOTE_SECONDS", 1)

    confirmar = MagicMock(return_value=0.0)

    async def _run() -> None:
        fal.schedule_fechar_apos_lote(
            nr_seq_caixa_rec=88,
            dt_recebimento="2026-08-25",
            confirmar_fn=confirmar,
            fluxo="cartao",
        )
        await asyncio.sleep(0.4)
        fal.schedule_fechar_apos_lote(
            nr_seq_caixa_rec=88,
            dt_recebimento="2026-08-25",
            confirmar_fn=confirmar,
            fluxo="pix",
        )
        await asyncio.sleep(1.3)

    asyncio.run(_run())
    confirmar.assert_called_once_with(88, "2026-08-25")

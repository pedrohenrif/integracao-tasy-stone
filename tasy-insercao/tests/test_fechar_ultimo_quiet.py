import asyncio
from unittest.mock import MagicMock

from tasy_insercao.infrastructure.messaging import fechar_debounce as fd


def test_quiet_remarca_e_fecha_ultimo(monkeypatch):
    monkeypatch.setattr(fd.settings, "FECHAR_ULTIMO_RECEB_ENABLED", True)
    monkeypatch.setattr(fd.settings, "FECHAR_ULTIMO_RECEB_SECONDS", 1)

    calls: list[tuple[int, str]] = []

    def confirmar(nr: int, dt: str) -> float:
        calls.append((nr, dt))
        return 0.0

    async def _run() -> None:
        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=10,
            dt_recebimento="2026-08-24",
            confirmar_fn=confirmar,
            serial="A",
        )
        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=10,
            dt_recebimento="2026-08-24",
            confirmar_fn=confirmar,
            serial="A",
        )
        await asyncio.sleep(1.3)

    asyncio.run(_run())
    assert calls == [(10, "2026-08-24")]


def test_cancel_evita_fechar_apos_troca(monkeypatch):
    monkeypatch.setattr(fd.settings, "FECHAR_ULTIMO_RECEB_ENABLED", True)
    monkeypatch.setattr(fd.settings, "FECHAR_ULTIMO_RECEB_SECONDS", 1)

    confirmar = MagicMock(return_value=0.0)

    async def _run() -> None:
        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=20,
            dt_recebimento="2026-08-24",
            confirmar_fn=confirmar,
            serial="B",
        )
        fd.cancel_fechar_recebimento(20)
        await asyncio.sleep(1.3)

    asyncio.run(_run())
    confirmar.assert_not_called()

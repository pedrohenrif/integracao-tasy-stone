from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from tasy_insercao.infrastructure.config import settings as settings_mod
from tasy_insercao.infrastructure.messaging import fechar_debounce as fd


def test_debounce_remarques_e_executa_uma_vez(monkeypatch):
    monkeypatch.setattr(settings_mod.settings, "FECHAR_RECEB_DEBOUNCE_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "FECHAR_RECEB_DEBOUNCE_SECONDS", 1)
    fd._pending.clear()

    async def _scenario() -> list[tuple[int, str]]:
        calls: list[tuple[int, str]] = []

        def confirmar(nr: int, dt: str) -> float:
            calls.append((nr, dt))
            return 0.0

        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=88,
            dt_recebimento="2026-08-19",
            confirmar_fn=confirmar,
            serial="AAA",
        )
        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=88,
            dt_recebimento="2026-08-19",
            confirmar_fn=confirmar,
            serial="AAA",
        )
        assert fd.pending_fechar_count() == 1
        await asyncio.sleep(1.3)
        return calls

    calls = asyncio.run(_scenario())
    assert calls == [(88, "2026-08-19")]
    assert fd.pending_fechar_count() == 0


def test_debounce_dois_recebimentos_independentes(monkeypatch):
    monkeypatch.setattr(settings_mod.settings, "FECHAR_RECEB_DEBOUNCE_ENABLED", True)
    monkeypatch.setattr(settings_mod.settings, "FECHAR_RECEB_DEBOUNCE_SECONDS", 1)
    fd._pending.clear()

    async def _scenario() -> list[int]:
        calls: list[int] = []

        def confirmar(nr: int, dt: str) -> float:
            calls.append(nr)
            return 0.0

        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=88,
            dt_recebimento="2026-08-19",
            confirmar_fn=confirmar,
            serial="A",
        )
        fd.schedule_fechar_recebimento(
            nr_seq_caixa_rec=99,
            dt_recebimento="2026-08-19",
            confirmar_fn=confirmar,
            serial="B",
        )
        assert fd.pending_fechar_count() == 2
        await asyncio.sleep(1.3)
        return calls

    calls = asyncio.run(_scenario())
    assert sorted(calls) == [88, 99]


def test_debounce_desligado_nao_agenda(monkeypatch):
    monkeypatch.setattr(settings_mod.settings, "FECHAR_RECEB_DEBOUNCE_ENABLED", False)
    fd._pending.clear()
    fd.schedule_fechar_recebimento(
        nr_seq_caixa_rec=1,
        dt_recebimento="2026-08-19",
        confirmar_fn=MagicMock(),
        serial="X",
    )
    assert fd.pending_fechar_count() == 0

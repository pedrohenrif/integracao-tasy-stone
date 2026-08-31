from __future__ import annotations

import json
from pathlib import Path

import stone_extracao.infrastructure.store.pix_lote_state as lote


def test_lote_fluxo_webhook_e_reserva(tmp_path, monkeypatch):
    state_file = tmp_path / "pix_lote_state.json"
    monkeypatch.setattr(lote, "_STATE_PATH", state_file)

    lote.marcar_aguardando_webhook("2026-08-25")
    st = lote.status_lote("2026-08-25")
    assert st["awaiting_webhook"] is True
    assert st["webhook_at"] is None
    assert lote.precisa_fallback_cartao("2026-08-25") is True

    lote.marcar_webhook_recebido("2026-08-25", pix_published=0)
    st = lote.status_lote("2026-08-25")
    assert st["awaiting_webhook"] is False
    assert st["webhook_at"]
    assert st["pix_published"] == 0

    assert lote.reservar_disparo_cartao("2026-08-25") is True
    assert lote.reservar_disparo_cartao("2026-08-25") is False
    assert lote.precisa_fallback_cartao("2026-08-25") is False

    lote.liberar_disparo_cartao("2026-08-25")
    assert lote.precisa_fallback_cartao("2026-08-25") is True
    assert lote.reservar_disparo_cartao("2026-08-25") is True

    lote.registrar_cartao_publicado("2026-08-25", 12)
    raw = json.loads(Path(state_file).read_text(encoding="utf-8"))
    assert raw["dates"]["2026-08-25"]["cartao_published"] == 12


def test_encontrar_iso_aguardando_unico(tmp_path, monkeypatch):
    state_file = tmp_path / "pix_lote_state.json"
    monkeypatch.setattr(lote, "_STATE_PATH", state_file)

    assert lote.encontrar_iso_aguardando() is None
    lote.marcar_aguardando_webhook("2026-08-20")
    assert lote.encontrar_iso_aguardando() == "2026-08-20"
    lote.marcar_aguardando_webhook("2026-08-21")
    assert lote.encontrar_iso_aguardando() is None

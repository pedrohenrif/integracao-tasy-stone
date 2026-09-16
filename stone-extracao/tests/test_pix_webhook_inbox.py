from stone_extracao.infrastructure.store.pix_webhook_inbox import listar_hits, registrar_hit


def test_inbox_registra_e_lista(tmp_path, monkeypatch):
    import stone_extracao.infrastructure.store.pix_webhook_inbox as inbox

    monkeypatch.setattr(inbox, "_PATH", tmp_path / "inbox.json")
    registrar_hit(
        method="POST",
        path="/pix/webhook",
        client_ip="1.2.3.4",
        forwarded_for="10.0.0.1",
        content_type="application/json",
        body_len=20,
        body_preview='{"type":"pix"}',
        event_type="pix",
        status="received",
    )
    data = listar_hits(limit=5)
    assert data["count"] == 1
    assert data["hits"][0]["event_type"] == "pix"
    assert data["hits"][0]["client_ip"] == "1.2.3.4"

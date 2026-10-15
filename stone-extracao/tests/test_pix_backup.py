from pathlib import Path

from stone_extracao.infrastructure.store.pix_backup import (
    linhas_pix_backup,
    listar_pix_backup,
    save_pix_conferencia,
    save_pix_csv_backup,
)


def _enable_backup(tmp_path, monkeypatch):
    from stone_extracao.infrastructure.store import pix_backup

    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_ENABLED", True)
    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_DIR", str(tmp_path / "xml_backup"))


def test_save_pix_csv_e_conferencia(tmp_path, monkeypatch):
    _enable_backup(tmp_path, monkeypatch)
    raw = b"id,status\nok1,paid\n"
    saved = save_pix_csv_backup(raw, reference_date="2026-09-15", source="webhook")
    assert saved is not None
    assert saved.path.is_file()
    assert saved.bytes_written == len(raw)
    latest = saved.path.parent / "stone_pix_20260915_latest.csv"
    assert latest.is_file()
    assert latest.read_bytes() == raw

    dest = save_pix_conferencia(
        reference_date="2026-09-15",
        payload={"ok": False, "publicados": 1, "fora_piloto": 1},
    )
    assert dest is not None
    listing = listar_pix_backup("2026-09-15")
    assert listing["date"] == "20260915"
    names = {f["name"] for f in listing["files"]}
    assert "stone_pix_20260915_latest.csv" in names
    assert "stone_pix_20260915_conferencia.json" in names
    assert listing["conferencia"]["fora_piloto"] == 1
    assert listing["conferencia"]["ok"] is False


def test_linhas_pix_backup_marca_publicados(tmp_path, monkeypatch):
    _enable_backup(tmp_path, monkeypatch)
    csv = (
        "id,status,pix_transaction__detail__operation,amount,"
        "pix_transaction__detail__provider_datetime,pix_transaction__terminal__serial_number\n"
        "ok1,paid,pay,1000,2026-09-15T10:00:00-03:00,PB09231S72079\n"
        "ok2,paid,pay,2000,2026-09-15T11:00:00-03:00,OUTROSERIAL\n"
    ).encode()
    save_pix_csv_backup(csv, reference_date="2026-09-15", source="webhook")
    save_pix_conferencia(
        reference_date="2026-09-15",
        payload={"ids_publicados": ["ok1"], "publicados": 1, "fora_piloto": 1, "source": "webhook"},
    )
    out = linhas_pix_backup("2026-09-15")
    assert out["has_csv"] is True
    by_id = {r["id_stone"]: r for r in out["items"]}
    assert by_id["ok1"]["publicado"] == "S"
    assert by_id["ok2"]["publicado"] == "N"
    assert by_id["ok2"]["ds_motivo"] == "fora_piloto"


def test_backup_desligado_nao_grava(tmp_path, monkeypatch):
    from stone_extracao.infrastructure.store import pix_backup

    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_ENABLED", False)
    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_DIR", str(tmp_path / "xml_backup"))
    assert save_pix_csv_backup(b"x", reference_date="2026-09-15") is None
    assert not list(Path(tmp_path).rglob("*.csv"))

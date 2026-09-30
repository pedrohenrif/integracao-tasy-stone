from pathlib import Path

from stone_extracao.infrastructure.store.pix_backup import (
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


def test_backup_desligado_nao_grava(tmp_path, monkeypatch):
    from stone_extracao.infrastructure.store import pix_backup

    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_ENABLED", False)
    monkeypatch.setattr(pix_backup.settings, "STONE_XML_BACKUP_DIR", str(tmp_path / "xml_backup"))
    assert save_pix_csv_backup(b"x", reference_date="2026-09-15") is None
    assert not list(Path(tmp_path).rglob("*.csv"))

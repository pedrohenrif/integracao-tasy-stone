from pathlib import Path

from stone_extracao.infrastructure.store.xml_backup import save_cartao_xml_backup


def test_save_cartao_xml_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STONE_XML_BACKUP_ENABLED", "true")
    monkeypatch.setenv("STONE_XML_BACKUP_DIR", "data/xml_backup")
    monkeypatch.setenv("STONE_MERCHANT_ID", "116852622")

    # reload settings after env
    from stone_extracao.infrastructure.config import settings as settings_mod

    settings_mod.settings = settings_mod.Settings()

    raw = b"<Conciliation><Header><StoneCode>116852622</StoneCode></Header></Conciliation>"
    result = save_cartao_xml_backup(raw, reference_date="20260731", tag="vazio")
    assert result is not None
    assert result.path.is_file()
    assert result.bytes_written == len(raw)
    latest = result.path.parent / "stone_cartao_20260731_latest.xml"
    assert latest.is_file()
    assert latest.read_bytes() == raw

from datetime import date
from unittest.mock import MagicMock

from tasy_insercao.infrastructure.persistence.catalog_queries import _periodos_cruzam
from tasy_insercao.infrastructure.persistence.postgres import StagingPostgresRepository


def test_periodos_cruzam():
    assert _periodos_cruzam(date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 18), date(2026, 10, 18))
    assert not _periodos_cruzam(
        date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 19), date(2026, 10, 20)
    )
    assert _periodos_cruzam(date(2026, 10, 17), None, date(2026, 10, 20), date(2026, 10, 21))


def test_alocacao_do_dia_sobrepoe_caixa_padrao():
    db = MagicMock()
    db.fetchone.side_effect = [
        ("PB09231X75906", 41, 700, "N"),
        (42, 801, "N"),
    ]
    cfg = StagingPostgresRepository(db).find_maquininha_config(
        "PB09231X75906", dt=date(2026, 10, 17)
    )
    assert cfg is not None
    assert cfg["cd_caixa"] == 42
    assert cfg["cd_transacao_financeira"] == 801
    assert db.fetchone.call_count == 2


def test_sem_alocacao_fica_caixa_padrao():
    db = MagicMock()
    db.fetchone.side_effect = [
        ("PB09231X75906", 41, 700, "N"),
        None,
    ]
    cfg = StagingPostgresRepository(db).find_maquininha_config(
        "PB09231X75906", dt=date(2026, 10, 16)
    )
    assert cfg is not None
    assert cfg["cd_caixa"] == 41
    assert cfg["cd_transacao_financeira"] == 700

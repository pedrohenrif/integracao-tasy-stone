from unittest.mock import MagicMock

from tasy_insercao.infrastructure.persistence.oracle import TasyOracleRepository


def test_ensure_reusa_unico_recebimento_do_caixa():
    """1 recebimento aberto por caixa+dia — serial nao cria outro."""
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.inserir_caixa_receb = MagicMock(return_value=99)

    db.fetchone.return_value = (88,)  # aberto do saldo

    nr = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 930, "SERIAL-A")

    assert nr == 88
    repo.inserir_caixa_receb.assert_not_called()
    db.fetchone.assert_called_once()


def test_ensure_cria_quando_nao_ha_aberto():
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.inserir_caixa_receb = MagicMock(return_value=99)

    db.fetchone.return_value = None

    nr = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 270, "SERIAL-B")

    assert nr == 99
    repo.inserir_caixa_receb.assert_called_once_with(50, "2026-08-23", 270)


def test_ensure_dois_seriais_mesmo_saldo_reusam_mesmo():
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.inserir_caixa_receb = MagicMock(return_value=99)
    db.fetchone.return_value = (88,)

    a = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 270, "SERIAL-A")
    b = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 270, "SERIAL-B")

    assert a == 88
    assert b == 88
    repo.inserir_caixa_receb.assert_not_called()

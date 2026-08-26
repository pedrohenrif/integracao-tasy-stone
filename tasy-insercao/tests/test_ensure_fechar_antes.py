from unittest.mock import MagicMock

from tasy_insercao.infrastructure.persistence.oracle import TasyOracleRepository


def test_ensure_fecha_outro_serial_antes_de_abrir():
    """Tasy: 1 lote aberto/caixa — ao abrir serial B, FECHAR o aberto de A."""
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.confirmar_caixa_receb_stone = MagicMock(return_value=0.0)
    repo.inserir_caixa_receb = MagicMock(return_value=99)

    db.fetchone.return_value = None  # sem aberto do serial B
    db.fetchall.return_value = [(88, "2026-08-23")]  # aberto do serial A

    nr = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 930, "SERIAL-B")

    assert nr == 99
    repo.confirmar_caixa_receb_stone.assert_called_once_with(88, "2026-08-23")
    repo.inserir_caixa_receb.assert_called_once_with(50, "2026-08-23", 930)


def test_ensure_reusa_mesmo_serial_e_fecha_orfaos():
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.confirmar_caixa_receb_stone = MagicMock(return_value=0.0)
    repo.inserir_caixa_receb = MagicMock(return_value=99)

    db.fetchone.return_value = (88,)  # aberto do serial A
    db.fetchall.return_value = [(77, "2026-08-23"), (88, "2026-08-23")]

    nr = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 930, "SERIAL-A")

    assert nr == 88
    repo.confirmar_caixa_receb_stone.assert_called_once_with(77, "2026-08-23")
    repo.inserir_caixa_receb.assert_not_called()


def test_ensure_mesmo_serial_sem_orfaos_nao_fecha():
    db = MagicMock()
    repo = TasyOracleRepository(db)
    repo.confirmar_caixa_receb_stone = MagicMock(return_value=0.0)

    db.fetchone.return_value = (88,)
    db.fetchall.return_value = [(88, "2026-08-23")]

    nr = repo.ensure_caixa_receb_aberto(50, "2026-08-23", 930, "SERIAL-A")

    assert nr == 88
    repo.confirmar_caixa_receb_stone.assert_not_called()

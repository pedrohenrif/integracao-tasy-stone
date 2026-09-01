from tasy_insercao.domain.integracao.filtro_piloto import (
    motivo_ignorar,
    parse_csv_ints,
    parse_csv_strs,
)


def test_parse_csv():
    assert parse_csv_ints("48, 10,x") == frozenset({48, 10})
    assert parse_csv_strs("A, B ,") == frozenset({"A", "B"})


def test_motivo_ignorar_serial(monkeypatch):
    monkeypatch.setattr(
        "tasy_insercao.domain.integracao.filtro_piloto.settings.INTEGRAR_SOMENTE_SERIAIS",
        "PB09231S72079",
    )
    monkeypatch.setattr(
        "tasy_insercao.domain.integracao.filtro_piloto.settings.INTEGRAR_SOMENTE_CAIXAS",
        "",
    )
    assert motivo_ignorar(serial="OUTRO", cd_caixa=48) is not None
    assert motivo_ignorar(serial="PB09231S72079", cd_caixa=48) is None


def test_motivo_ignorar_caixa(monkeypatch):
    monkeypatch.setattr(
        "tasy_insercao.domain.integracao.filtro_piloto.settings.INTEGRAR_SOMENTE_SERIAIS",
        "",
    )
    monkeypatch.setattr(
        "tasy_insercao.domain.integracao.filtro_piloto.settings.INTEGRAR_SOMENTE_CAIXAS",
        "48",
    )
    assert motivo_ignorar(serial="X", cd_caixa=10) is not None
    assert motivo_ignorar(serial="X", cd_caixa=48) is None
    assert motivo_ignorar(serial="X", cd_caixa=None) is None

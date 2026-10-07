from tasy_insercao.domain.integracao.filtro_piloto import (
    motivo_ignorar,
    parse_csv_ints,
    parse_csv_strs,
)


def test_parse_csv():
    assert parse_csv_ints("48, 10,x") == frozenset({48, 10})
    assert parse_csv_strs("A, B ,") == frozenset({"A", "B"})


def test_motivo_ignorar_nao_usa_allowlist_env():
    assert motivo_ignorar(serial="OUTRO", cd_caixa=10) is None
    assert motivo_ignorar(serial="PB09231S72079", cd_caixa=48) is None
    assert motivo_ignorar(serial="X", cd_caixa=None) is None

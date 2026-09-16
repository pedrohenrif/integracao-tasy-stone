from tasy_insercao.infrastructure.persistence.debug_queries import (
    FiltrosPainel,
    _where,
    parse_csv_ints,
    parse_csv_tokens,
)


def test_parse_csv_tokens():
    assert parse_csv_tokens("credit_card, pix") == ["credit_card", "pix"]
    assert parse_csv_ints("5,7, x") == [5, 7]


def test_where_multi_tipo_e_status():
    sql, params = _where(
        FiltrosPainel(cd_tipo_transacao="credit_card,pix", cd_status="5,7")
    )
    assert "ANY(%(tipos)s)" in sql
    assert params["tipos"] == ["credit_card"]
    assert "pix" in sql.lower()
    assert "ANY(%(cd_statuses)s)" in sql
    assert params["cd_statuses"] == [5, 7]


def test_where_tipo_unico_ainda_funciona():
    sql, params = _where(FiltrosPainel(cd_tipo_transacao="debit_card"))
    assert params["tipos"] == ["debit_card"]
    assert "ANY(%(tipos)s)" in sql

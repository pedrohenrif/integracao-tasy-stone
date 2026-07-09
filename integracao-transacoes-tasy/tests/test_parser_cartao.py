from decimal import Decimal
from pathlib import Path

from app.parsers.cartao_xml import parse_cartao_xml_file
from app.schemas.cartao import TipoTransacaoCartao

SAMPLE_PATH = (
    Path(__file__).resolve().parents[2] / "stone_movimento_20260708_cartao.xml"
)


def test_sample_file_exists():
    assert SAMPLE_PATH.is_file(), f"Sample não encontrado: {SAMPLE_PATH}"


def test_parse_cartao_sample_count():
    txs = parse_cartao_xml_file(SAMPLE_PATH)
    assert len(txs) > 0
    # sample conhecido: 187 transactions com Captures>=1
    assert len(txs) == 187


def test_parse_first_transaction_fields():
    txs = parse_cartao_xml_file(SAMPLE_PATH)
    first = next(t for t in txs if t.id_stone == "28963791511463")

    assert first.vl_transacao == Decimal("7.000000")
    assert first.nr_serie_maquininha == "PB09231S72079"
    assert first.cd_autorizacao == "520973"
    assert first.qt_parcelas == 1
    assert first.ie_transacao_parcelada is False
    assert first.cd_bandeira == "2"
    assert first.account_type == 3
    assert first.cd_tipo_transacao == TipoTransacaoCartao.PREPAID_DEBIT
    assert first.stone_code == "116852622"
    assert first.dt_movimentacao.year == 2026
    assert first.dt_movimentacao.month == 7
    assert first.dt_movimentacao.day == 8


def test_all_have_id_and_terminal():
    txs = parse_cartao_xml_file(SAMPLE_PATH)
    for tx in txs:
        assert tx.id_stone
        assert tx.nr_serie_maquininha
        assert tx.vl_transacao > 0

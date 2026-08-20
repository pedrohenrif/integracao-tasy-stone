from decimal import Decimal
from pathlib import Path

from stone_extracao.infrastructure.parsers.cartao_xml import parse_cartao_xml_file
from stone_extracao.domain.cartao.models import TipoTransacaoCartao

SAMPLE = Path(__file__).resolve().parents[2] / "stone_movimento_20260708_cartao.xml"


def test_parse_sample():
    assert SAMPLE.is_file()
    txs = parse_cartao_xml_file(SAMPLE)
    assert len(txs) == 187
    first = next(t for t in txs if t.id_stone == "28963791511463")
    assert first.vl_transacao == Decimal("7.000000")
    assert first.nr_serie_maquininha == "PB09231S72079"
    assert first.cd_tipo_transacao == TipoTransacaoCartao.PREPAID_DEBIT

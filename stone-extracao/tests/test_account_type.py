from stone_extracao.domain.cartao.models import TipoTransacaoCartao
from stone_extracao.infrastructure.parsers.cartao_xml import _map_account_type


def test_account_type_stone_layout_22():
    assert _map_account_type("1")[1] == TipoTransacaoCartao.DEBIT_CARD
    assert _map_account_type("2")[1] == TipoTransacaoCartao.CREDIT_CARD
    assert _map_account_type("3")[1] == TipoTransacaoCartao.PREPAID_DEBIT
    assert _map_account_type("4")[1] == TipoTransacaoCartao.PREPAID_CREDIT
    assert _map_account_type("4")[0] == 4

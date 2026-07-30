from datetime import datetime
from decimal import Decimal

from tasy_insercao.application.use_cases.integrar_transacao_pix import pix_para_cartao_tasy
from tasy_insercao.domain.integracao.models import TipoTransacaoCartao, TransacaoPix


def test_pix_adapta_para_debito_tasy():
    pix = TransacaoPix(
        id_stone="A2896o6HJEvEhX3g3cUL1pMhCHx",
        e2e_id="E003603052026070821539d0e37007b2",
        vl_transacao=Decimal("7.00"),
        dt_movimentacao=datetime(2026, 7, 8, 21, 53, 47),
        nr_serie_maquininha="PB09231S72079",
    )
    cartao = pix_para_cartao_tasy(pix)
    assert cartao.cd_tipo_transacao == TipoTransacaoCartao.PIX
    assert cartao.cd_autorizacao == pix.e2e_id
    assert cartao.qt_parcelas == 1

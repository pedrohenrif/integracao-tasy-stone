from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import StatusIntegracao, TipoTransacaoCartao, TransacaoCartao


def _tx() -> TransacaoCartao:
    return TransacaoCartao(
        id_stone="28963791511463",
        vl_transacao=Decimal("7"),
        dt_movimentacao=datetime(2026, 7, 8, 7, 28, 45),
        nr_serie_maquininha="PB09231S72079",
        cd_autorizacao="520973",
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
        cd_bandeira="2",
    )


def test_fluxo_com_tesouraria_chama_fechar_e_nao_documento():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = {
        "cd_caixa": 10,
        "cd_transacao_financeira": 123,
    }
    staging.ensure_registro.return_value = 99
    staging.get_bandeira_tasy.return_value = 21
    tasy.ensure_caixa_saldo_diario.return_value = 50
    tasy.inserir_caixa_receb.return_value = 88
    tasy.inserir_movto_cartao.return_value = 77
    tasy.fechar_caixa_receb.return_value = 0.0

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_caixa_receb.assert_called_once()
    tasy.fechar_caixa_receb.assert_called_once_with(88, "2026-07-08")
    tasy.inserir_documento.assert_not_called()
    assert "confirmado" in result.mensagem.lower()

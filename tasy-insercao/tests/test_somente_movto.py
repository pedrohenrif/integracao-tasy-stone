from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import StatusIntegracao, TipoTransacaoCartao, TransacaoCartao


def _tx(serial: str = "PB09218373216") -> TransacaoCartao:
    return TransacaoCartao(
        id_stone="tmkt-id-1",
        vl_transacao=Decimal("40.00"),
        dt_movimentacao=datetime(2026, 10, 6, 10, 0, 0),
        nr_serie_maquininha=serial,
        cd_autorizacao="XYZ",
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
        cd_bandeira="1",
    )


def test_caixa_somente_movto_nao_abre_caixa_receb():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = {
        "nr_serie_maquininha": "PB09218373216",
        "cd_caixa": 13,
        "cd_transacao_financeira": None,
        "ie_somente_movto": "S",
    }
    staging.ensure_registro.return_value = 7
    staging.get_bandeira_tasy.return_value = 19
    tasy.inserir_movto_cartao_sem_tesouraria.return_value = 555

    with patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.motivo_ignorar",
        return_value=None,
    ):
        result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.SOMENTE_MOVTO
    tasy.ensure_caixa_saldo_diario.assert_not_called()
    tasy.inserir_caixa_receb.assert_not_called()
    tasy.inserir_movto_cartao_sem_tesouraria.assert_called_once()
    movto_params = tasy.inserir_movto_cartao_sem_tesouraria.call_args[0][0]
    assert movto_params["ie_lib_caixa"] == "S"
    assert result.nr_seq_caixa_receb is None
    assert staging.update_status.call_args[0][1] == StatusIntegracao.SOMENTE_MOVTO.value


def test_caixa_normal_sem_tf_e_ignorado():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = {
        "nr_serie_maquininha": "PB09231S72079",
        "cd_caixa": 48,
        "cd_transacao_financeira": None,
        "ie_somente_movto": "N",
    }
    staging.ensure_registro.return_value = 3

    with patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.motivo_ignorar",
        return_value=None,
    ):
        result = IntegrarTransacaoCartao(staging, tasy).execute(_tx("PB09231S72079"))

    assert result.status == StatusIntegracao.IGNORADO
    tasy.inserir_movto_cartao_sem_tesouraria.assert_not_called()
    tasy.ensure_caixa_saldo_diario.assert_not_called()

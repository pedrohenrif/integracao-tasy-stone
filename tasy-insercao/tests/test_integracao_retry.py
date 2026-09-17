from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import StatusIntegracao, TipoTransacaoCartao, TransacaoCartao
from tasy_insercao.domain.integracao.policies import is_retryable_error
from tasy_insercao.infrastructure.messaging.rabbit import delay_for_attempt


def _tx() -> TransacaoCartao:
    return TransacaoCartao(
        id_stone="28963791511463",
        vl_transacao=Decimal("7"),
        dt_movimentacao=datetime(2026, 7, 8, 7, 28, 45),
        nr_serie_maquininha="PB09231S72079",
        cd_autorizacao="520973",
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.PREPAID_DEBIT,
        cd_bandeira="2",
    )


def test_idempotente_status_5():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = (99, StatusIntegracao.INTEGRADO.value, "ok")
    tasy.exists_movto_by_id_stone.return_value = True
    tasy.ensure_documento_por_id_stone.return_value = False
    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())
    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_movto_cartao.assert_not_called()


def test_reintegra_quando_movto_tasy_cancelado():
    """PG INTEGRADO + Oracle sem movto ativo (DT_CANCELAMENTO) → reinsere."""
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = (99, StatusIntegracao.INTEGRADO.value, "ok")
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = {
        "cd_caixa": 15,
        "cd_transacao_financeira": 271,
    }
    staging.ensure_registro.return_value = 99
    staging.get_bandeira_tasy.return_value = 21
    tasy.ensure_caixa_saldo_diario.return_value = 50
    tasy.ensure_caixa_receb_aberto.return_value = 88
    tasy.inserir_movto_cartao.return_value = 77
    tasy.upsert_documento_agregado.return_value = 7.0

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_movto_cartao.assert_called_once()
    tasy.ensure_caixa_receb_aberto.assert_called_once()


def test_retryable_connection_error():
    assert is_retryable_error(Exception("ORA-12541: TNS:no listener"))
    assert is_retryable_error(Exception("could not connect to server"))
    assert not is_retryable_error(ValueError("Mapeamento Tasy não encontrado"))


def test_delay_backoff():
    assert delay_for_attempt(1) == 30
    assert delay_for_attempt(5) == 600

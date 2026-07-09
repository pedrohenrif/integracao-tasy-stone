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
    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())
    assert result.status == StatusIntegracao.INTEGRADO
    tasy.exists_movto_by_id_stone.assert_not_called()


def test_retryable_connection_error():
    assert is_retryable_error(Exception("ORA-12541: TNS:no listener"))
    assert is_retryable_error(Exception("could not connect to server"))
    assert not is_retryable_error(ValueError("Mapeamento Tasy não encontrado"))


def test_delay_backoff():
    assert delay_for_attempt(1) == 30
    assert delay_for_attempt(5) == 600

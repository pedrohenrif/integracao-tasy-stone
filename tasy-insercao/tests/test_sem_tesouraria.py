from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import StatusIntegracao, TipoTransacaoCartao, TransacaoCartao


def _tx(serial: str = "SERIAL_NOVO_XYZ") -> TransacaoCartao:
    return TransacaoCartao(
        id_stone="99998888777766",
        vl_transacao=Decimal("15.50"),
        dt_movimentacao=datetime(2026, 7, 26, 10, 0, 0),
        nr_serie_maquininha=serial,
        cd_autorizacao="ABC123",
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
        cd_bandeira="2",
    )


def test_sem_tesouraria_insere_movto_sem_caixa():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = None
    staging.ensure_registro.return_value = 42
    staging.get_bandeira_tasy.return_value = 21
    tasy.inserir_movto_cartao_sem_tesouraria.return_value = 777

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.SEM_TESOURARIA
    assert result.retryable is False
    tasy.ensure_caixa_saldo_diario.assert_not_called()
    tasy.inserir_caixa_receb.assert_not_called()
    tasy.inserir_documento.assert_not_called()
    tasy.inserir_movto_cartao_sem_tesouraria.assert_called_once()
    assert staging.update_status.call_args[0][0] == 42
    assert staging.update_status.call_args[0][1] == StatusIntegracao.SEM_TESOURARIA.value
    assert "SEM_TESOURARIA" in staging.update_status.call_args[0][2]


def test_sem_tesouraria_idempotente():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = (
        10,
        StatusIntegracao.SEM_TESOURARIA.value,
        "SEM_TESOURARIA | ...",
    )
    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())
    assert result.status == StatusIntegracao.SEM_TESOURARIA
    tasy.inserir_movto_cartao_sem_tesouraria.assert_not_called()

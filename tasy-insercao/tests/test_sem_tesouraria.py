from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

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


def test_sem_caixa_ignore_nao_insere_oracle():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = None
    staging.ensure_registro.return_value = 42

    with patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.sem_caixa_policy",
        return_value="ignore",
    ), patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.motivo_ignorar",
        return_value=None,
    ):
        result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.IGNORADO
    assert result.retryable is False
    tasy.inserir_movto_cartao_sem_tesouraria.assert_not_called()
    tasy.ensure_caixa_saldo_diario.assert_not_called()
    assert staging.ensure_registro.call_args[0][1] == StatusIntegracao.IGNORADO.value
    assert "IGNORADO" in staging.ensure_registro.call_args[0][2]


def test_sem_tesouraria_insere_quando_policy_insert():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = None
    staging.ensure_registro.return_value = 42
    staging.get_bandeira_tasy.return_value = 21
    tasy.inserir_movto_cartao_sem_tesouraria.return_value = 777

    with patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.sem_caixa_policy",
        return_value="insert",
    ), patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.motivo_ignorar",
        return_value=None,
    ):
        result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.SEM_TESOURARIA
    tasy.inserir_movto_cartao_sem_tesouraria.assert_called_once()
    assert staging.update_status.call_args[0][1] == StatusIntegracao.SEM_TESOURARIA.value


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


def test_ignorado_idempotente():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = (
        11,
        StatusIntegracao.IGNORADO.value,
        "IGNORADO | ...",
    )
    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())
    assert result.status == StatusIntegracao.IGNORADO
    tasy.inserir_movto_cartao_sem_tesouraria.assert_not_called()


def test_allowlist_caixa_ignora_mesmo_com_config():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = None
    tasy.exists_movto_by_id_stone.return_value = False
    staging.find_maquininha_config.return_value = {
        "cd_caixa": 10,
        "cd_transacao_financeira": 1,
    }
    staging.ensure_registro.return_value = 55

    with patch(
        "tasy_insercao.application.use_cases.integrar_transacao_cartao.motivo_ignorar",
        return_value="caixa 10 fora do piloto",
    ):
        result = IntegrarTransacaoCartao(staging, tasy).execute(_tx("PB09231S72079"))

    assert result.status == StatusIntegracao.IGNORADO
    tasy.ensure_caixa_saldo_diario.assert_not_called()
    tasy.inserir_movto_cartao.assert_not_called()

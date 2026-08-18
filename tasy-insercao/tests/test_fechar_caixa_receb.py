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


def _setup_ok():
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
    return staging, tasy


def test_documento_sempre_depois_movto_e_antes_do_fechar():
    staging, tasy = _setup_ok()
    order: list[str] = []
    tasy.inserir_documento.side_effect = lambda *_a, **_k: order.append("doc")
    tasy.fechar_caixa_receb.side_effect = lambda *_a, **_k: (
        order.append("fechar") or 0.0
    )

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_documento.assert_called_once()
    doc_params = tasy.inserir_documento.call_args[0][0]
    assert "nr_seq_caixa" not in doc_params
    assert "nr_seq_saldo_caixa" not in doc_params
    assert doc_params["nr_seq_caixa_rec"] == 88
    tasy.fechar_caixa_receb.assert_called_once_with(88, "2026-07-08")
    assert order == ["doc", "fechar"]
    assert "confirmado" in result.mensagem.lower()


def test_fechar_falha_purge_oracle_e_status_9_reintegrar():
    staging, tasy = _setup_ok()
    tasy.fechar_caixa_receb.side_effect = Exception(
        "ORA-20011: Já existe um lote aberto para este caixa!"
    )
    tasy.purge_stone_transaction.return_value = {
        "ok": True,
        "deleted": {"movto": 1, "docs": 1, "caixa_receb": 1, "parcelas": 0},
    }

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.CONFIRMACAO_PENDENTE
    assert result.retryable is False
    assert result.nr_seq_caixa_receb is None
    tasy.purge_stone_transaction.assert_called_once()
    assert "REINTEGRAR" in result.mensagem
    staging.update_status.assert_called_with(
        99,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        result.mensagem,
    )


def test_reprocesso_status_9_com_movto_so_tenta_fechar():
    staging = MagicMock()
    tasy = MagicMock()
    staging.get_by_id_stone.return_value = (
        42,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        "REINTEGRAR | antigo",
    )
    tasy.exists_movto_by_id_stone.return_value = True
    tasy.ensure_documento_por_id_stone.return_value = False
    tasy.get_caixa_receb_para_confirmar.return_value = {
        "nr_seq_caixa_rec": 88,
        "dt_recebimento": "2026-07-08",
        "ja_fechado": False,
    }
    tasy.fechar_caixa_receb.return_value = 0.0

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_caixa_receb.assert_not_called()
    tasy.inserir_movto_cartao.assert_not_called()
    tasy.inserir_documento.assert_not_called()
    tasy.fechar_caixa_receb.assert_called_once_with(88, "2026-07-08")


def test_reprocesso_status_9_sem_movto_reintegra_do_zero():
    staging, tasy = _setup_ok()
    staging.get_by_id_stone.return_value = (
        99,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        "REINTEGRAR | Oracle removido",
    )
    tasy.exists_movto_by_id_stone.return_value = False
    tasy.fechar_caixa_receb.return_value = 0.0

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.inserir_caixa_receb.assert_called_once()
    tasy.inserir_movto_cartao.assert_called_once()
    tasy.inserir_documento.assert_called_once()
    tasy.fechar_caixa_receb.assert_called_once()
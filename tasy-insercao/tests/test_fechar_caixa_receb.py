from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import StatusIntegracao, TipoTransacaoCartao, TransacaoCartao


def _tx(id_stone: str = "28963791511463") -> TransacaoCartao:
    return TransacaoCartao(
        id_stone=id_stone,
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
    tasy.ensure_caixa_receb_aberto.return_value = 88
    tasy.inserir_movto_cartao.return_value = 77
    tasy.upsert_documento_agregado.return_value = 7.0
    return staging, tasy


def test_unifica_recebimento_e_documento_sem_fechar_automatico():
    staging, tasy = _setup_ok()
    order: list[str] = []
    tasy.ensure_caixa_receb_aberto.side_effect = lambda *a, **k: (
        order.append("receb") or 88
    )
    tasy.inserir_movto_cartao.side_effect = lambda *a, **k: (order.append("movto") or 77)
    tasy.upsert_documento_agregado.side_effect = lambda **k: (
        order.append("doc") or 7.0
    )

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    assert order == ["receb", "movto", "doc"]
    tasy.ensure_caixa_receb_aberto.assert_called_once_with(50, "2026-07-08", 123)
    tasy.upsert_documento_agregado.assert_called_once()
    doc_kw = tasy.upsert_documento_agregado.call_args.kwargs
    assert doc_kw["nr_seq_caixa_rec"] == 88
    assert doc_kw["nr_seq_trans_financ"] == 123
    tasy.fechar_caixa_receb.assert_not_called()
    tasy.inserir_caixa_receb.assert_not_called()
    assert "doc_agregado" in result.mensagem.lower() or "caixa_receb=88" in result.mensagem


def test_segunda_tx_reusa_mesmo_recebimento():
    staging, tasy = _setup_ok()
    tasy.ensure_caixa_receb_aberto.return_value = 88
    tasy.upsert_documento_agregado.return_value = 15.0
    tasy.inserir_movto_cartao.return_value = 78

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx("outro-id"))

    assert result.status == StatusIntegracao.INTEGRADO
    assert result.nr_seq_caixa_receb == 88
    tasy.ensure_caixa_receb_aberto.assert_called_once()
    assert tasy.upsert_documento_agregado.call_args.kwargs["nr_seq_caixa_rec"] == 88
    tasy.fechar_caixa_receb.assert_not_called()


def test_fechar_falha_purge_so_se_unico_movto():
    staging, tasy = _setup_ok()
    # Caminho status 9 com movto existente → só FECHAR
    staging.get_by_id_stone.return_value = (
        99,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        "REINTEGRAR",
    )
    tasy.exists_movto_by_id_stone.return_value = True
    tasy.get_caixa_receb_para_confirmar.return_value = {
        "nr_seq_caixa_rec": 88,
        "dt_recebimento": "2026-07-08",
        "ja_fechado": False,
    }
    tasy.fechar_caixa_receb.side_effect = Exception("ORA-20011: CTB")
    tasy.count_movtos_caixa_receb.return_value = 1
    tasy.purge_stone_transaction.return_value = {
        "ok": True,
        "deleted": {"movto": 1, "docs": 1, "caixa_receb": 1},
    }

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.CONFIRMACAO_PENDENTE
    tasy.purge_stone_transaction.assert_called_once()
    assert "REINTEGRAR" in result.mensagem


def test_fechar_falha_nao_purge_recebimento_compartilhado():
    staging, tasy = _setup_ok()
    staging.get_by_id_stone.return_value = (
        99,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        "REINTEGRAR",
    )
    tasy.exists_movto_by_id_stone.return_value = True
    tasy.get_caixa_receb_para_confirmar.return_value = {
        "nr_seq_caixa_rec": 88,
        "dt_recebimento": "2026-07-08",
        "ja_fechado": False,
    }
    tasy.fechar_caixa_receb.side_effect = Exception("ORA-20011: CTB")
    tasy.count_movtos_caixa_receb.return_value = 5

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.CONFIRMACAO_PENDENTE
    tasy.purge_stone_transaction.assert_not_called()
    assert result.nr_seq_caixa_receb == 88


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
    tasy.ensure_caixa_receb_aberto.assert_not_called()
    tasy.inserir_movto_cartao.assert_not_called()
    tasy.fechar_caixa_receb.assert_called_once_with(88, "2026-07-08")


def test_reprocesso_status_9_sem_movto_reintegra_do_zero():
    staging, tasy = _setup_ok()
    staging.get_by_id_stone.return_value = (
        99,
        StatusIntegracao.CONFIRMACAO_PENDENTE.value,
        "REINTEGRAR | Oracle removido",
    )
    tasy.exists_movto_by_id_stone.return_value = False

    result = IntegrarTransacaoCartao(staging, tasy).execute(_tx())

    assert result.status == StatusIntegracao.INTEGRADO
    tasy.ensure_caixa_receb_aberto.assert_called_once()
    tasy.inserir_movto_cartao.assert_called_once()
    tasy.upsert_documento_agregado.assert_called_once()
    tasy.fechar_caixa_receb.assert_not_called()

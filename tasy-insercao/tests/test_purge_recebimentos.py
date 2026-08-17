from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tasy_insercao.application.use_cases import purge_recebimentos_stone as purge_mod
from tasy_insercao.application.use_cases.purge_recebimentos_stone import (
    CONFIRM_PHRASE,
    PurgeRequest,
    confirm_purge,
    preview_purge,
)


@pytest.fixture(autouse=True)
def _clear_tokens():
    purge_mod._PURGE_TOKENS.clear()
    yield
    purge_mod._PURGE_TOKENS.clear()


def test_nm_usuario_obrigatorio():
    with pytest.raises(ValueError, match="nm_usuario"):
        preview_purge(PurgeRequest(nm_usuario="  ", id_stones=["1"]))


def test_escopo_minimo_obrigatorio():
    with pytest.raises(ValueError, match="escopo mínimo"):
        preview_purge(PurgeRequest(nm_usuario="stone"))


def test_confirm_exige_frase_excluir():
    with pytest.raises(ValueError, match="EXCLUIR"):
        confirm_purge(
            PurgeRequest(nm_usuario="stone", id_stones=["abc"]),
            confirm_token="tok",
            confirm_phrase="apagar",
        )


@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.registrar_acao_log")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.TasyOracleRepository")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.listar_registros_por_id_stones")
def test_preview_e_confirm_ok(mock_list, mock_repo_cls, _mock_log):
    mock_list.return_value = [
        {
            "nr_sequencia": 10,
            "id_stone": "ABC123",
            "cd_caixa": 48,
            "cd_status": 5,
            "vl_transacao": 10.5,
            "dt_movimentacao": date(2026, 8, 12),
        }
    ]
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.preview_purge_stone.return_value = {
        "nr_seq_movto": 1,
        "nr_seq_caixa_rec": 2,
        "vl_transacao": 10.5,
        "dt_transacao": "2026-08-12",
        "ja_fechado": False,
        "qtd_docs": 1,
        "qtd_parcelas": 1,
    }
    repo.purge_stone_transaction.return_value = {
        "ok": True,
        "deleted": {"docs": 1, "parcelas": 1, "movto": 1, "caixa_receb": 1},
    }

    prev = preview_purge(
        PurgeRequest(nm_usuario="stone", id_stones=["ABC123"]),
        user={"nr_sequencia": 1, "ds_login": "admin"},
    )
    assert prev["totais"]["elegiveis"] == 1
    assert prev["confirm_token"]
    assert prev["items"][0]["can_purge"] is True

    with patch(
        "tasy_insercao.application.use_cases.purge_recebimentos_stone.atualizar_status_registro"
    ) as mock_upd:
        out = confirm_purge(
            PurgeRequest(nm_usuario="stone", id_stones=["ABC123"]),
            confirm_token=prev["confirm_token"],
            confirm_phrase=CONFIRM_PHRASE,
            user={"nr_sequencia": 1, "ds_login": "admin"},
        )
    assert out["ok"] == 1
    assert out["falhas"] == 0
    repo.purge_stone_transaction.assert_called_once()
    mock_upd.assert_called_once()
    assert mock_upd.call_args[0][1] == 1  # status pendente


@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.registrar_acao_log")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.TasyOracleRepository")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.listar_registros_por_id_stones")
def test_fechado_bloqueado_sem_flag(mock_list, mock_repo_cls, _mock_log):
    mock_list.return_value = [
        {
            "nr_sequencia": 10,
            "id_stone": "ABC123",
            "cd_caixa": 48,
            "cd_status": 5,
            "vl_transacao": 10.5,
            "dt_movimentacao": date(2026, 8, 12),
        }
    ]
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.preview_purge_stone.return_value = {
        "nr_seq_movto": 1,
        "nr_seq_caixa_rec": 2,
        "vl_transacao": 10.5,
        "dt_transacao": "2026-08-12",
        "ja_fechado": True,
        "qtd_docs": 1,
        "qtd_parcelas": 0,
    }

    prev = preview_purge(PurgeRequest(nm_usuario="stone", id_stones=["ABC123"], allow_fechado=False))
    assert prev["totais"]["elegiveis"] == 0
    assert prev["totais"]["bloqueados"] == 1
    assert prev["items"][0]["can_purge"] is False


@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.registrar_acao_log")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.TasyOracleRepository")
@patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.listar_registros_por_id_stones")
def test_confirm_token_so_uma_vez(mock_list, mock_repo_cls, _mock_log):
    mock_list.return_value = [
        {
            "nr_sequencia": 10,
            "id_stone": "ABC123",
            "cd_caixa": 48,
            "cd_status": 5,
            "vl_transacao": 1,
            "dt_movimentacao": date(2026, 8, 12),
        }
    ]
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.preview_purge_stone.return_value = {
        "nr_seq_movto": 1,
        "nr_seq_caixa_rec": None,
        "vl_transacao": 1,
        "dt_transacao": "2026-08-12",
        "ja_fechado": False,
        "qtd_docs": 0,
        "qtd_parcelas": 0,
    }
    repo.purge_stone_transaction.return_value = {"ok": True, "deleted": {"movto": 1}}

    prev = preview_purge(PurgeRequest(nm_usuario="stone", id_stones=["ABC123"]))
    token = prev["confirm_token"]

    with patch(
        "tasy_insercao.application.use_cases.purge_recebimentos_stone.atualizar_status_registro"
    ):
        confirm_purge(
            PurgeRequest(nm_usuario="stone", id_stones=["ABC123"]),
            confirm_token=token,
            confirm_phrase=CONFIRM_PHRASE,
        )

    with pytest.raises(ValueError, match="Token"):
        confirm_purge(
            PurgeRequest(nm_usuario="stone", id_stones=["ABC123"]),
            confirm_token=token,
            confirm_phrase=CONFIRM_PHRASE,
        )


def test_nao_stone_sem_match_oracle_nao_e_elegivel():
    """Se o Oracle não achar movto do usuário, item fica bloqueado (protege manual)."""
    with (
        patch(
            "tasy_insercao.application.use_cases.purge_recebimentos_stone.listar_registros_por_id_stones"
        ) as mock_list,
        patch(
            "tasy_insercao.application.use_cases.purge_recebimentos_stone.TasyOracleRepository"
        ) as mock_repo_cls,
        patch("tasy_insercao.application.use_cases.purge_recebimentos_stone.registrar_acao_log"),
    ):
        mock_list.return_value = [
            {
                "nr_sequencia": 99,
                "id_stone": "MANUAL1",
                "cd_caixa": 1,
                "cd_status": 5,
                "vl_transacao": 9,
                "dt_movimentacao": date(2026, 8, 12),
            }
        ]
        repo = MagicMock()
        mock_repo_cls.return_value = repo
        repo.preview_purge_stone.return_value = None

        prev = preview_purge(PurgeRequest(nm_usuario="stone", id_stones=["MANUAL1"]))
        assert prev["totais"]["sem_oracle"] == 1
        assert prev["totais"]["elegiveis"] == 0

from datetime import date
from unittest.mock import MagicMock, patch

from tasy_insercao.infrastructure.auth import portal_acao_log as mod


def test_listar_acao_logs_paginado_com_filtros():
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur
    fake_conn.__enter__.return_value = fake_conn

    fake_cur.fetchone.return_value = {"total": 2}
    fake_cur.fetchall.return_value = [
        {
            "nr_sequencia": 1,
            "nr_seq_usuario": None,
            "ds_login": "sistema",
            "ds_acao": "scheduler_cartao_erro",
            "nr_seq_registro": None,
            "id_stone": None,
            "ds_antes": None,
            "ds_depois": {"error": "boom"},
            "ds_obs": "falhou",
            "dt_evento": None,
            "ds_nome": None,
        }
    ]

    with patch.object(mod, "_connect", return_value=fake_conn):
        out = mod.listar_acao_logs(
            limit=50,
            offset=0,
            acao="scheduler",
            login="sistema",
            data_de=date(2026, 8, 1),
            data_ate=date(2026, 8, 17),
        )

    assert out["total"] == 2
    assert out["limit"] == 50
    assert out["offset"] == 0
    assert len(out["items"]) == 1
    assert out["items"][0]["ds_acao"] == "scheduler_cartao_erro"
    assert fake_cur.execute.call_count == 2

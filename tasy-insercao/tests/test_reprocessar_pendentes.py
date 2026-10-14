import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

from tasy_insercao.application.use_cases.reprocessar import (
    _STATUS_PENDENTES_ERRO,
    reprocessar_pendentes_dia,
)
from tasy_insercao.domain.integracao.models import StatusIntegracao


def test_status_pendentes_nao_inclui_integrado_nem_somente_movto():
    assert StatusIntegracao.PENDENTE.value in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.ERRO_RETRY.value in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.ERRO_DEFINITIVO.value in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.CONFIRMACAO_PENDENTE.value in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.INTEGRADO.value not in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.SOMENTE_MOVTO.value not in _STATUS_PENDENTES_ERRO
    assert StatusIntegracao.IGNORADO.value not in _STATUS_PENDENTES_ERRO


def test_pendentes_dia_reenfileira_so_erro_e_respeita_serial():
    rows = [
        {"nr_sequencia": 10, "cd_status": 7, "id_stone": "dlq-1"},
        {"nr_sequencia": 11, "cd_status": 6, "id_stone": "retry-1"},
        {"nr_sequencia": 12, "cd_status": 5, "id_stone": "ok-1"},
        {"nr_sequencia": 13, "cd_status": 11, "id_stone": "tmkt-1"},
    ]

    async def _run():
        with (
            patch(
                "tasy_insercao.application.use_cases.reprocessar.listar_registros",
                return_value=rows,
            ) as mock_list,
            patch(
                "tasy_insercao.application.use_cases.reprocessar.reprocessar_selecionados",
                new_callable=AsyncMock,
            ) as mock_sel,
            patch("tasy_insercao.application.use_cases.reprocessar.registrar_acao_log"),
        ):
            mock_sel.return_value = {
                "enfileirados": 2,
                "ids_stone": ["dlq-1", "retry-1"],
                "ignorados": [],
                "erros": [],
            }
            res = await reprocessar_pendentes_dia(
                date(2026, 10, 12),
                nr_serie="PB0923A171142",
                user={"nr_sequencia": 1, "ds_login": "pedro"},
            )

        filtros = mock_list.call_args[0][0]
        assert filtros.nr_serie == "PB0923A171142"
        assert "7" in str(filtros.cd_status)
        assert "5" not in str(filtros.cd_status).split(",")
        mock_sel.assert_awaited_once()
        assert mock_sel.await_args[0][0] == [10, 11]
        assert res["enfileirados"] == 2
        assert res["mode"] == "pendentes_dia"
        assert "PB0923A171142" in (res["mensagem"] or "")

    asyncio.run(_run())


def test_pendentes_dia_vazio_nao_chama_lote():
    async def _run():
        with (
            patch(
                "tasy_insercao.application.use_cases.reprocessar.listar_registros",
                return_value=[],
            ),
            patch(
                "tasy_insercao.application.use_cases.reprocessar.reprocessar_selecionados",
                new_callable=AsyncMock,
            ) as mock_sel,
            patch("tasy_insercao.application.use_cases.reprocessar.registrar_acao_log"),
        ):
            res = await reprocessar_pendentes_dia(date(2026, 10, 4))

        mock_sel.assert_not_awaited()
        assert res["enfileirados"] == 0
        assert res["mode"] == "pendentes_dia"

    asyncio.run(_run())

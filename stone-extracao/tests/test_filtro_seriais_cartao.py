import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from stone_extracao.application.use_cases.extrair_conciliacao_cartao import ExtrairConciliacaoCartao
from stone_extracao.domain.cartao.models import TipoTransacaoCartao, TransacaoCartao


def _tx(serial: str, id_stone: str) -> TransacaoCartao:
    return TransacaoCartao(
        id_stone=id_stone,
        vl_transacao=Decimal("10.00"),
        dt_movimentacao=datetime(2026, 8, 1, 12, 0, 0),
        nr_serie_maquininha=serial,
        cd_autorizacao="A1",
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
        cd_bandeira="2",
    )


def test_filtro_terminals_cartao(monkeypatch):
    monkeypatch.setattr(
        "stone_extracao.application.use_cases.extrair_conciliacao_cartao.save_cartao_xml_backup",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "stone_extracao.application.use_cases.extrair_conciliacao_cartao.analyze_cartao_totais",
        lambda raw, txs: MagicMock(
            avisos=[],
            tem_divergencia=False,
            soma_transacoes=0,
            total_arquivo=0,
            divergencia=0,
            por_bandeira_tipo={},
        ),
    )
    monkeypatch.setattr(
        "stone_extracao.infrastructure.config.settings.settings.STONE_USE_SAMPLE",
        False,
    )

    client = MagicMock()
    client.fetch = AsyncMock(return_value=b"<xml/>")
    parser = MagicMock()
    # force sync parse path (no parse_with_stats)
    del parser.parse_with_stats
    parser.parse.return_value = [
        _tx("PB09231S72079", "1"),
        _tx("OUTRO", "2"),
    ]
    publisher = MagicMock()
    publisher.publish_cartao = AsyncMock()

    result = asyncio.get_event_loop().run_until_complete(
        ExtrairConciliacaoCartao(client, parser, publisher).execute(
            "20260801",
            terminals={"PB09231S72079"},
        )
    )
    assert result.parsed_count == 1
    assert result.published_count == 1
    assert result.transactions[0].nr_serie_maquininha == "PB09231S72079"
    publisher.publish_cartao.assert_awaited_once()

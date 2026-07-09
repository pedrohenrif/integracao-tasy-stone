from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.schemas.cartao import TipoTransacaoCartao, TransacaoCartao
from app.services.tasy_service import STATUS_INTEGRADO, TasyService
from app.utils.money import map_stone_brand, map_tipo_para_api, to_float_money


def test_to_float_money_decimal():
    assert to_float_money(Decimal("7.000000")) == 7.0


def test_to_float_money_brl_string():
    assert to_float_money("R$ 1.304,50") == 1304.5


def test_map_brand_mastercard():
    assert map_stone_brand("2") == "mastercard"
    assert map_stone_brand(None) == "none"


def test_map_tipo_prepaid_as_debit():
    assert map_tipo_para_api("prepaid_debit") == "debit_card"
    assert map_tipo_para_api("credit_card") == "credit_card"


def test_idempotente_quando_status_5():
    pg = MagicMock()
    oracle = MagicMock()
    pg.fetchone.return_value = (99, STATUS_INTEGRADO, "ok")

    svc = TasyService(pg, oracle)
    tx = TransacaoCartao(
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
    result = svc.processar_transacao_cartao(tx)
    assert result.status == STATUS_INTEGRADO
    assert "idempotente" in result.mensagem.lower()
    oracle.fetchone.assert_not_called()


def test_calcular_vencimento_credito_pula_fds():
    pg = MagicMock()
    oracle = MagicMock()
    svc = TasyService(pg, oracle)
    # 2026-07-08 (quarta) + 30 = 2026-08-07 (sexta) — dia útil
    venc = svc._calcular_vencimento("credit_card", date(2026, 7, 8))
    assert venc == date(2026, 8, 7)

    debito = svc._calcular_vencimento("debit_card", date(2026, 7, 8))
    assert debito == date(2026, 7, 9)

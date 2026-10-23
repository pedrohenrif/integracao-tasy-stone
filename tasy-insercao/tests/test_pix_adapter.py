from datetime import date, datetime, timezone
from decimal import Decimal

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.application.use_cases.integrar_transacao_pix import pix_para_cartao_tasy
from tasy_insercao.domain.integracao.models import TipoTransacaoCartao, TransacaoPix


def test_pix_adapta_para_debito_tasy():
    pix = TransacaoPix(
        id_stone="A2896o6HJEvEhX3g3cUL1pMhCHx",
        e2e_id="E003603052026070821539d0e37007b2",
        vl_transacao=Decimal("7.00"),
        dt_movimentacao=datetime(2026, 7, 8, 21, 53, 47),
        nr_serie_maquininha="PB09231S72079",
    )
    cartao = pix_para_cartao_tasy(pix)
    assert cartao.cd_tipo_transacao == TipoTransacaoCartao.PIX
    assert cartao.cd_autorizacao == pix.e2e_id
    assert cartao.qt_parcelas == 1
    # naive UTC 21:53 → 18:53 BRT no mesmo dia
    assert cartao.dt_movimentacao.date() == date(2026, 7, 8)
    assert cartao.dt_movimentacao.hour == 18


def test_pix_utc_depois_das_21h_cai_no_dia_brt():
    pix = TransacaoPix(
        id_stone="pix-4-reais-cantina",
        e2e_id="E00360305202610210037xxxx",
        vl_transacao=Decimal("4.00"),
        dt_movimentacao=datetime(2026, 10, 21, 0, 37, 0),
        nr_serie_maquininha="PB09243M78791",
        reference_date="2026-10-21",
    )
    cartao = pix_para_cartao_tasy(pix)
    assert cartao.dt_movimentacao.date() == date(2026, 10, 20)
    assert cartao.dt_movimentacao.hour == 21
    assert cartao.dt_movimentacao.minute == 37
    assert cartao.reference_date == "2026-10-20"


def test_pix_aware_utc_depois_das_21h_cai_no_dia_brt():
    pix = TransacaoPix(
        id_stone="pix-4-reais-z",
        vl_transacao=Decimal("4.00"),
        dt_movimentacao=datetime(2026, 10, 21, 0, 37, 0, tzinfo=timezone.utc),
        nr_serie_maquininha="PB09243M78791",
    )
    cartao = pix_para_cartao_tasy(pix)
    assert cartao.dt_movimentacao.date() == date(2026, 10, 20)
    assert cartao.reference_date == "2026-10-20"


def test_data_saldo_aware_utc_vira_dia_brt():
    uc = IntegrarTransacaoCartao(staging=None, tasy=None)  # type: ignore[arg-type]
    dt = datetime(2026, 10, 21, 0, 37, 0, tzinfo=timezone.utc)
    assert uc._data_saldo(dt) == date(2026, 10, 20)


def test_data_saldo_cartao_naive_nao_converte_utc():
    uc = IntegrarTransacaoCartao(staging=None, tasy=None)  # type: ignore[arg-type]
    dt = datetime(2026, 10, 20, 21, 37, 0)
    assert uc._data_saldo(dt) == date(2026, 10, 20)

from decimal import Decimal

from stone_extracao.domain.cartao.models import TipoTransacaoCartao, TransacaoCartao
from stone_extracao.infrastructure.parsers.cartao_totais import analyze_cartao_totais
from datetime import datetime


def test_analyze_without_payment_section():
    xml = """<?xml version="1.0"?>
    <Consolidation>
      <Header><StoneCode>1</StoneCode><ReferenceDate>20260726</ReferenceDate></Header>
      <FinancialTransactions>
        <Transaction>
          <AcquirerTransactionKey>1</AcquirerTransactionKey>
          <CapturedAmount>10.00</CapturedAmount>
          <CaptureLocalDateTime>20260726100000</CaptureLocalDateTime>
          <AccountType>2</AccountType>
          <BrandId>2</BrandId>
          <Events><Captures>1</Captures></Events>
          <Poi><SerialNumber>ABC</SerialNumber></Poi>
        </Transaction>
      </FinancialTransactions>
    </Consolidation>
    """
    txs = [
        TransacaoCartao(
            id_stone="1",
            vl_transacao=Decimal("10.00"),
            dt_movimentacao=datetime(2026, 7, 26, 10, 0, 0),
            nr_serie_maquininha="ABC",
            cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
            cd_bandeira="2",
            account_type=2,
        )
    ]
    result = analyze_cartao_totais(xml, txs)
    assert result.soma_transacoes == Decimal("10.00")
    assert result.tem_totais_arquivo is False
    assert result.tem_divergencia is False
    assert any("sem seção" in a.lower() or "XML sem" in a for a in result.avisos)


def test_analyze_with_payments_divergence():
    xml = """<?xml version="1.0"?>
    <Consolidation>
      <Header><StoneCode>1</StoneCode></Header>
      <FinancialTransactions></FinancialTransactions>
      <Payments>
        <Payment><Amount>100.00</Amount></Payment>
      </Payments>
    </Consolidation>
    """
    txs = [
        TransacaoCartao(
            id_stone="1",
            vl_transacao=Decimal("99.99"),
            dt_movimentacao=datetime(2026, 7, 26, 10, 0, 0),
            nr_serie_maquininha="ABC",
            cd_tipo_transacao=TipoTransacaoCartao.CREDIT_CARD,
            cd_bandeira="2",
        )
    ]
    result = analyze_cartao_totais(xml, txs)
    assert result.tem_totais_arquivo is True
    assert result.tem_divergencia is True
    assert result.divergencia == Decimal("-0.01")

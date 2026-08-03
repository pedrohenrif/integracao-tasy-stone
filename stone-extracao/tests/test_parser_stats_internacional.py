from stone_extracao.infrastructure.parsers.cartao_xml import parse_cartao_xml_with_stats

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Conciliation>
  <Header>
    <StoneCode>116852622</StoneCode>
    <ReferenceDate>20260731</ReferenceDate>
  </Header>
  <FinancialTransactions>
    <Transaction>
      <Events><Captures>0</Captures><Payments>1</Payments></Events>
      <AcquirerTransactionKey>111</AcquirerTransactionKey>
      <CapturedAmount>10.00</CapturedAmount>
      <CaptureLocalDateTime>20260731120000</CaptureLocalDateTime>
      <AccountType>2</AccountType>
      <BrandId>171</BrandId>
      <International>False</International>
      <NumberOfInstallments>1</NumberOfInstallments>
      <Poi><SerialNumber>ABC123</SerialNumber></Poi>
    </Transaction>
    <Transaction>
      <Events><Captures>1</Captures></Events>
      <AcquirerTransactionKey>222</AcquirerTransactionKey>
      <CapturedAmount>25.50</CapturedAmount>
      <CaptureLocalDateTime>20260731130000</CaptureLocalDateTime>
      <AccountType>1</AccountType>
      <BrandId>171</BrandId>
      <International>True</International>
      <NumberOfInstallments>1</NumberOfInstallments>
      <Poi><SerialNumber>XYZ999</SerialNumber></Poi>
    </Transaction>
  </FinancialTransactions>
</Conciliation>
"""


def test_stats_skip_sem_capture_e_internacional():
    result = parse_cartao_xml_with_stats(XML)
    assert result.stats.transactions_total == 2
    assert result.stats.skipped_no_capture == 1
    assert result.stats.accepted == 1
    assert len(result.transactions) == 1
    tx = result.transactions[0]
    assert tx.id_stone == "222"
    assert tx.ie_internacional is True
    assert result.stats.international_true == 1

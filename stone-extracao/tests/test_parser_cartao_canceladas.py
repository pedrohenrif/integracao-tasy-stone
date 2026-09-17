from stone_extracao.infrastructure.parsers.cartao_xml import parse_cartao_xml_with_stats

_HEADER = """
<Conciliation>
  <Header>
    <StoneCode>116852622</StoneCode>
    <ReferenceDate>20260913</ReferenceDate>
  </Header>
  <FinancialTransactions>
"""
_FOOTER = """
  </FinancialTransactions>
</Conciliation>
"""


def _tx(
    key: str,
    *,
    events: str,
    extra: str = "",
    amount: str = "10.00",
) -> str:
    return f"""
    <Transaction>
      <Events>{events}</Events>
      <AcquirerTransactionKey>{key}</AcquirerTransactionKey>
      <CapturedAmount>{amount}</CapturedAmount>
      <CaptureLocalDateTime>20260913120000</CaptureLocalDateTime>
      <AccountType>2</AccountType>
      <BrandId>171</BrandId>
      <NumberOfInstallments>1</NumberOfInstallments>
      <Poi><SerialNumber>PB0921B676098</SerialNumber></Poi>
      {extra}
    </Transaction>
"""


def test_skip_events_cancellations_and_block():
    xml = (
        _HEADER
        + _tx("ok-1", events="<Captures>1</Captures>")
        + _tx(
            "35663330989441",
            events="<Cancellations>1</Cancellations><Captures>1</Captures>",
            amount="360.000000",
            extra="""
      <Cancellations>
        <Cancellation>
          <ReturnedAmount>360.000000</ReturnedAmount>
        </Cancellation>
      </Cancellations>
""",
        )
        + _FOOTER
    )
    result = parse_cartao_xml_with_stats(xml)
    assert result.stats.transactions_total == 2
    assert result.stats.accepted == 1
    assert result.stats.skipped_cancelled == 1
    assert [t.id_stone for t in result.transactions] == ["ok-1"]


def test_skip_cancellations_block_even_if_events_count_zero():
    xml = (
        _HEADER
        + _tx(
            "void-block",
            events="<Captures>1</Captures><Cancellations>0</Cancellations>",
            extra="<Cancellations><Cancellation/></Cancellations>",
        )
        + _FOOTER
    )
    result = parse_cartao_xml_with_stats(xml)
    assert result.stats.skipped_cancelled == 1
    assert result.transactions == []


def test_skip_chargebacks_and_refunds():
    xml = (
        _HEADER
        + _tx("cb-1", events="<Captures>1</Captures><Chargebacks>1</Chargebacks>")
        + _tx(
            "cbr-1",
            events="<Captures>1</Captures>",
            extra="<ChargebackRefunds><ChargebackRefund/></ChargebackRefunds>",
        )
        + _tx("ok-2", events="<Captures>1</Captures>")
        + _FOOTER
    )
    result = parse_cartao_xml_with_stats(xml)
    assert result.stats.skipped_chargeback == 2
    assert result.stats.accepted == 1
    assert [t.id_stone for t in result.transactions] == ["ok-2"]

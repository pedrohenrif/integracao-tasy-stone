from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class TipoTransacaoCartao(str, Enum):
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    PREPAID_DEBIT = "prepaid_debit"
    UNKNOWN = "unknown"


class TransacaoCartao(BaseModel):
    """Payload normalizado de uma transação de cartão Stone (Layout 2.2)."""

    id_stone: str = Field(..., description="AcquirerTransactionKey (NSU)")
    vl_transacao: Decimal = Field(..., description="CapturedAmount em reais")
    dt_movimentacao: datetime
    nr_serie_maquininha: str
    cd_autorizacao: str | None = None
    qt_parcelas: int = 1
    ie_transacao_parcelada: bool = False
    cd_tipo_transacao: TipoTransacaoCartao
    cd_bandeira: str | None = None
    account_type: int | None = None
    initiator_transaction_key: str | None = None
    stone_code: str | None = None
    reference_date: str | None = None


class EventoFilaCartao(BaseModel):
    """Envelope publicado na fila stone.cartao.transactions."""

    event_type: str = "cartao.transaction"
    source: str = "stone.conciliation"
    received_at: datetime
    transaction: TransacaoCartao

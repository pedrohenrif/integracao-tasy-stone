from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransacaoPix(BaseModel):
    """Contrato de domínio da transação PIX (publicado na fila stone.pix.transactions)."""

    id_stone: str = Field(..., description="ID Stone da cobrança PIX")
    e2e_id: str | None = Field(None, description="End-to-end ID bancário")
    vl_transacao: Decimal = Field(..., description="Valor em reais (centavos/100)")
    dt_movimentacao: datetime
    nr_serie_maquininha: str
    status: str = "paid"
    payment_method: str = "pix"
    merchant_document: str | None = None
    fee_amount: Decimal | None = None
    payer_name: str | None = None
    payer_document: str | None = None
    operation: str | None = Field(None, description="pay / refund / ...")
    stone_code: str | None = None
    reference_date: str | None = None


class EventoFilaPix(BaseModel):
    """Envelope da fila stone.pix.transactions (separado do cartão)."""

    event_type: str = "pix.transaction"
    source: str = "stone.conciliation.pix"
    received_at: datetime
    attempt: int = Field(default=1, ge=1)
    first_seen_at: datetime | None = None
    last_error: str | None = None
    transaction: TransacaoPix

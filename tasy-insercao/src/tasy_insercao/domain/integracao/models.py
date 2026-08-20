from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class TipoTransacaoCartao(str, Enum):
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    PREPAID_DEBIT = "prepaid_debit"
    PIX = "pix"
    UNKNOWN = "unknown"


class TransacaoCartao(BaseModel):
    id_stone: str
    vl_transacao: Decimal
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
    ie_internacional: bool | None = None


class EventoFilaCartao(BaseModel):
    """Mesmo contrato publicado por stone-extracao (cartão)."""

    event_type: str = "cartao.transaction"
    source: str = "stone.conciliation"
    received_at: datetime
    attempt: int = Field(default=1, ge=1)
    first_seen_at: datetime | None = None
    last_error: str | None = None
    transaction: TransacaoCartao


class TransacaoPix(BaseModel):
    """Contrato PIX publicado por stone-extracao (fila separada)."""

    id_stone: str
    e2e_id: str | None = None
    vl_transacao: Decimal
    dt_movimentacao: datetime
    nr_serie_maquininha: str
    status: str = "paid"
    payment_method: str = "pix"
    merchant_document: str | None = None
    fee_amount: Decimal | None = None
    payer_name: str | None = None
    payer_document: str | None = None
    operation: str | None = None
    stone_code: str | None = None
    reference_date: str | None = None


class EventoFilaPix(BaseModel):
    event_type: str = "pix.transaction"
    source: str = "stone.conciliation.pix"
    received_at: datetime
    attempt: int = Field(default=1, ge=1)
    first_seen_at: datetime | None = None
    last_error: str | None = None
    transaction: TransacaoPix


class StatusIntegracao(int, Enum):
    PENDENTE = 1
    PROCESSANDO = 2
    INTEGRADO = 5
    ERRO_RETRY = 6
    ERRO_DEFINITIVO = 7
    # Movto cartão no Tasy sem caixa_saldo_diario / caixa_receb (serial sem cadastro)
    SEM_TESOURARIA = 8
    # FECHAR falhou: Oracle é removido; painel status 9 = reintegrar do zero
    CONFIRMACAO_PENDENTE = 9


class ResultadoIntegracao(BaseModel):
    id_stone: str
    status: StatusIntegracao
    mensagem: str
    retryable: bool = False
    nr_sequencia_pg: int | None = None
    nr_seq_caixa_receb: int | None = None
    fluxo: str = "cartao"
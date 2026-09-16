from __future__ import annotations

import logging
from decimal import Decimal

# BrandId Stone (Layout 2.2 oficial) → nome canônico
# https://conciliacao.stone.com.br/reference/brandid
STONE_BRAND_ID_MAP: dict[str, str] = {
    "1": "visa",
    "2": "mastercard",
    "3": "amex",
    "4": "cabal",
    "5": "unionpay",
    "9": "hipercard",
    "171": "elo",  # Elo (NÃO é Ticket — bug antigo mapeava 171→ticket)
}

# Nome / alias → cd_bandeira da tabela local `bandeiras` (Cotolengo)
BANDEIRA_LOCAL_ID: dict[str, int] = {
    "visa": 1,
    "mastercard": 2,
    "elo": 3,
    "alelo": 4,
    "amex": 5,
    "american express": 5,
    "american_express": 5,
    "hipercard": 6,
    # Ticket / VR — só se a Stone enviar o nome; BrandId oficial de Ticket não está na doc 2.2
    "ticket": 7,
    "cabal": 8,
    "unionpay": 9,
}

# Tipo API Stone → cd_tipo_transacao local (mapeamento_transacoes_tasy)
TIPO_LOCAL_ID: dict[str, int] = {
    "credit_card": 1,
    "debit_card": 2,
    "pix": 3,
    "prepaid_credit": 6,  # AccountType 4 — bandeiras Tasy 25/27/28 (crédito pré-pago)
}


def to_float_money(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if not value or not isinstance(value, str):
        return 0.0
    try:
        cleaned = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        logging.warning("Valor inválido '%s' → 0.0", value)
        return 0.0


def map_stone_brand(brand_id: str | None) -> str:
    if not brand_id:
        return "none"
    key = str(brand_id).strip()
    return STONE_BRAND_ID_MAP.get(key, key.lower())


def map_tipo_para_api(tipo: str) -> str:
    """
    AccountType 3 (pré-pago débito) → débito normal.
    AccountType 4 (pré-pago crédito) permanece Pre_pago (bandeiras 25/27/28).
    """
    if tipo == "credit_card":
        return "credit_card"
    if tipo in ("prepaid_credit", "PREPAID_CREDIT"):
        return "prepaid_credit"
    if tipo in ("debit_card", "prepaid_debit", "PREPAID_DEBIT"):
        return "debit_card"
    if tipo == "pix":
        return "pix"
    return tipo


def is_debito_tasy(tipo_api: str) -> bool:
    """Débito, PIX e débito pré-pago (já normalizado) usam ie_tipo_cartao=D."""
    return tipo_api in ("debit_card", "pix")


def map_tipo_para_local(tipo_api: str) -> int | None:
    return TIPO_LOCAL_ID.get(tipo_api)


def map_bandeira_para_local(bandeira: str | None) -> int | None:
    if not bandeira or bandeira == "none":
        return None
    key = str(bandeira).strip().lower()
    if key in BANDEIRA_LOCAL_ID:
        return BANDEIRA_LOCAL_ID[key]
    # BrandId Stone numérico → nome → id local
    nome = STONE_BRAND_ID_MAP.get(key)
    if nome:
        return BANDEIRA_LOCAL_ID.get(nome)
    return None


RETRYABLE_ERROR_MARKERS = (
    "connect",
    "connection",
    "timeout",
    "timed out",
    "network",
    "ora-03113",
    "ora-03114",
    "ora-03135",
    "ora-12541",
    "ora-12514",
    "ora-12170",
    "dpapi",
    "could not connect",
    "server closed",
    "broken pipe",
    "temporarily unavailable",
    "deadlock",
    "lock wait",
)


def is_retryable_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in RETRYABLE_ERROR_MARKERS)

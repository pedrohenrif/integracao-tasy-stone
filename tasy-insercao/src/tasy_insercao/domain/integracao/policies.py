from __future__ import annotations

import logging
from decimal import Decimal

STONE_BRAND_ID_MAP: dict[str, str] = {
    "1": "visa",
    "2": "mastercard",
    "3": "amex",
    "4": "elo",
    "5": "hipercard",
    "6": "diners",
    "9": "sorocred",
    "171": "ticket",
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
    if tipo == "credit_card":
        return "credit_card"
    if tipo in ("debit_card", "prepaid_debit"):
        return "debit_card"
    return tipo


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

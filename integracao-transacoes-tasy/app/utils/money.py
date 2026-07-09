from __future__ import annotations

import logging
from decimal import Decimal


def to_float_money(value) -> float:
    """Normaliza valor monetário (Decimal/str BR/float) para float usado nos binds Oracle."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if not value or not isinstance(value, str):
        return 0.0
    try:
        cleaned = (
            value.replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        return float(cleaned)
    except (ValueError, TypeError):
        logging.warning("Não foi possível converter valor '%s' para float. Usando 0.0.", value)
        return 0.0


# BrandId Stone Conciliation Layout 2.2 → ds_bandeira_api (mapeamento_transacoes_tasy)
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


def map_stone_brand(brand_id: str | None) -> str:
    if not brand_id:
        return "none"
    key = str(brand_id).strip()
    return STONE_BRAND_ID_MAP.get(key, key.lower())


def map_tipo_para_api(tipo: str) -> str:
    """
    Normaliza tipo da fila para ds_tipo_transacao_api do GA111.
    prepaid_debit é tratado como debit_card no Tasy.
    """
    if tipo in ("credit_card",):
        return "credit_card"
    if tipo in ("debit_card", "prepaid_debit"):
        return "debit_card"
    return tipo

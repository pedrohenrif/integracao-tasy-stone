from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

from stone_extracao.domain.cartao.models import TipoTransacaoCartao, TransacaoCartao

# AccountType Stone Conciliation Layout 2.2
# 1=débito | 2=crédito | 3/4=pré-pago (prepaid_debit)
_ACCOUNT_TYPE_MAP: dict[int, TipoTransacaoCartao] = {
    1: TipoTransacaoCartao.DEBIT_CARD,
    2: TipoTransacaoCartao.CREDIT_CARD,
    3: TipoTransacaoCartao.PREPAID_DEBIT,
    4: TipoTransacaoCartao.PREPAID_DEBIT,
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(parent: ET.Element, name: str, default: str | None = None) -> str | None:
    for child in parent:
        if _local(child.tag) == name:
            text = (child.text or "").strip()
            return text if text else default
    return default


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _local(child.tag) == name:
            return child
    return None


def _parse_stone_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _map_account_type(raw: str | None) -> tuple[int | None, TipoTransacaoCartao]:
    if raw is None:
        return None, TipoTransacaoCartao.UNKNOWN
    try:
        code = int(raw)
    except ValueError:
        return None, TipoTransacaoCartao.UNKNOWN
    return code, _ACCOUNT_TYPE_MAP.get(code, TipoTransacaoCartao.UNKNOWN)


def _extract_terminal(tx: ET.Element) -> str:
    poi = _find_child(tx, "Poi")
    if poi is not None:
        serial = _find_text(poi, "SerialNumber")
        if serial:
            return serial

    initiator = _find_text(tx, "InitiatorTransactionKey") or ""
    if "-" in initiator:
        return initiator.split("-", 1)[0]
    return initiator or "UNKNOWN"


def _has_capture(tx: ET.Element) -> bool:
    events = _find_child(tx, "Events")
    if events is None:
        return False
    captures = _find_text(events, "Captures", "0") or "0"
    try:
        return int(captures) >= 1
    except ValueError:
        return False


def _parse_transaction(
    tx: ET.Element,
    *,
    stone_code: str | None,
    reference_date: str | None,
) -> TransacaoCartao | None:
    if not _has_capture(tx):
        return None

    id_stone = _find_text(tx, "AcquirerTransactionKey")
    if not id_stone:
        return None

    amount = _parse_decimal(_find_text(tx, "CapturedAmount"))
    if amount is None:
        amount = _parse_decimal(_find_text(tx, "AuthorizedAmount"))
    if amount is None:
        return None

    dt_mov = _parse_stone_datetime(_find_text(tx, "CaptureLocalDateTime"))
    if dt_mov is None:
        dt_mov = _parse_stone_datetime(_find_text(tx, "AuthorizationDateTime"))
    if dt_mov is None:
        return None

    parcelas_raw = _find_text(tx, "NumberOfInstallments", "1") or "1"
    try:
        qt_parcelas = max(int(parcelas_raw), 1)
    except ValueError:
        qt_parcelas = 1

    account_type, tipo = _map_account_type(_find_text(tx, "AccountType"))

    return TransacaoCartao(
        id_stone=id_stone,
        vl_transacao=amount,
        dt_movimentacao=dt_mov,
        nr_serie_maquininha=_extract_terminal(tx),
        cd_autorizacao=_find_text(tx, "IssuerAuthorizationCode"),
        qt_parcelas=qt_parcelas,
        ie_transacao_parcelada=qt_parcelas > 1,
        cd_tipo_transacao=tipo,
        cd_bandeira=_find_text(tx, "BrandId"),
        account_type=account_type,
        initiator_transaction_key=_find_text(tx, "InitiatorTransactionKey"),
        stone_code=stone_code,
        reference_date=reference_date,
    )


def parse_cartao_xml(content: str | bytes) -> list[TransacaoCartao]:
    """Parseia XML Conciliation Layout 2.2 e retorna apenas transações capturadas."""
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    root = ET.fromstring(content)
    header = _find_child(root, "Header")
    stone_code = _find_text(header, "StoneCode") if header is not None else None
    reference_date = _find_text(header, "ReferenceDate") if header is not None else None

    financial = _find_child(root, "FinancialTransactions")
    if financial is None:
        return []

    result: list[TransacaoCartao] = []
    for child in financial:
        if _local(child.tag) != "Transaction":
            continue
        parsed = _parse_transaction(
            child,
            stone_code=stone_code,
            reference_date=reference_date,
        )
        if parsed is not None:
            result.append(parsed)
    return result


def parse_cartao_xml_file(path: str | Path) -> list[TransacaoCartao]:
    file_path = Path(path)
    return parse_cartao_xml(file_path.read_bytes())

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from stone_extracao.domain.pix.models import TransacaoPix

_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    # normaliza +00:00 → +0000 para strptime %z em alguns casos
    if re.search(r"[+-]\d{2}:\d{2}$", raw):
        raw = raw[:-3] + raw[-2:]
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _centavos_para_reais(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _extract_stone_code(additional_data: str | None) -> str | None:
    if not additional_data:
        return None
    match = re.search(r"name=Cliente,\s*value=(\d+)", additional_data)
    return match.group(1) if match else None


@dataclass
class ParsePixStats:
    rows_total: int = 0
    accepted: int = 0
    skipped_status: int = 0
    skipped_operation: int = 0
    skipped_no_id: int = 0
    skipped_no_amount: int = 0
    skipped_no_date: int = 0
    skipped_samples: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows_total": self.rows_total,
            "accepted": self.accepted,
            "skipped_status": self.skipped_status,
            "skipped_operation": self.skipped_operation,
            "skipped_no_id": self.skipped_no_id,
            "skipped_no_amount": self.skipped_no_amount,
            "skipped_no_date": self.skipped_no_date,
            "skipped_samples": self.skipped_samples[:20],
        }

    def summary(self) -> str:
        return (
            f"linhas={self.rows_total} | aceitas(paid/pay)={self.accepted} | "
            f"status={self.skipped_status} | operacao={self.skipped_operation} | "
            f"sem_id={self.skipped_no_id} | sem_valor={self.skipped_no_amount} | "
            f"sem_data={self.skipped_no_date}"
        )


@dataclass
class ParsePixResult:
    transactions: list[TransacaoPix]
    stats: ParsePixStats


def _note_skip(stats: ParsePixStats, reason: str, row: dict[str, str]) -> None:
    if len(stats.skipped_samples) >= 20:
        return
    stats.skipped_samples.append(
        {
            "reason": reason,
            "id": (row.get("id") or "").strip()[:80],
            "status": (row.get("status") or "").strip()[:40],
            "serial": (row.get("pix_transaction__terminal__serial_number") or "").strip()[:40],
        }
    )


def parse_pix_csv_with_stats(content: str | bytes) -> ParsePixResult:
    """
    Parseia extrato PIX Stone.
    O sample usa extensão .xml, mas o conteúdo é CSV (centavos).
    Filtra status=paid e operation=pay.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    result: list[TransacaoPix] = []
    stats = ParsePixStats()

    for row in reader:
        stats.rows_total += 1
        status = (row.get("status") or "").strip().lower()
        operation = (row.get("pix_transaction__detail__operation") or "").strip().lower()
        if status != "paid":
            stats.skipped_status += 1
            _note_skip(stats, "status", row)
            continue
        if operation and operation != "pay":
            stats.skipped_operation += 1
            _note_skip(stats, "operation", row)
            continue

        id_stone = (row.get("id") or "").strip()
        if not id_stone:
            stats.skipped_no_id += 1
            _note_skip(stats, "no_id", row)
            continue

        amount = _centavos_para_reais(row.get("amount") or row.get("pix_transaction__paid_amount"))
        if amount is None:
            stats.skipped_no_amount += 1
            _note_skip(stats, "no_amount", row)
            continue

        dt_mov = _parse_dt(row.get("pix_transaction__detail__provider_datetime")) or _parse_dt(
            row.get("created_at")
        )
        if dt_mov is None:
            stats.skipped_no_date += 1
            _note_skip(stats, "no_date", row)
            continue

        terminal = (row.get("pix_transaction__terminal__serial_number") or "").strip() or "UNKNOWN"
        fee = _centavos_para_reais(row.get("pix_transaction__fee_amount"))
        additional = row.get("pix_transaction__additional_data")

        stats.accepted += 1
        result.append(
            TransacaoPix(
                id_stone=id_stone,
                e2e_id=(row.get("pix_transaction__e2e_id") or "").strip() or None,
                vl_transacao=amount,
                dt_movimentacao=dt_mov,
                nr_serie_maquininha=terminal,
                status=status,
                payment_method=(row.get("payment_method") or "pix").strip() or "pix",
                merchant_document=(row.get("merchant__document") or "").strip() or None,
                fee_amount=fee,
                payer_name=(row.get("pix_transaction__payer__name") or "").strip() or None,
                payer_document=(row.get("pix_transaction__payer__document") or "").strip() or None,
                operation=operation or "pay",
                stone_code=_extract_stone_code(additional),
                reference_date=dt_mov.strftime("%Y-%m-%d"),
            )
        )
    return ParsePixResult(transactions=result, stats=stats)


def parse_pix_csv(content: str | bytes) -> list[TransacaoPix]:
    return parse_pix_csv_with_stats(content).transactions


def parse_pix_file(path: str | Path) -> list[TransacaoPix]:
    return parse_pix_csv(Path(path).read_bytes())

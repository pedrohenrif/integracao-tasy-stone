"""Backup físico dos XMLs de conciliação Stone (cartão) na VM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class XmlBackupResult:
    path: Path
    bytes_written: int
    reference_date: str


def _backup_root() -> Path:
    """
    Pasta de backup.
    Relativo ao CWD do serviço (NSSM AppDirectory = stone-extracao/).
    """
    configured = (settings.STONE_XML_BACKUP_DIR or "data/xml_backup").strip()
    root = Path(configured)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def save_cartao_xml_backup(
    content: bytes | str,
    *,
    reference_date: str,
    merchant_id: str | None = None,
    tag: str | None = None,
) -> XmlBackupResult | None:
    """
    Grava o XML bruto retornado pela Stone.

    Estrutura:
      {STONE_XML_BACKUP_DIR}/cartao/{YYYY}/{YYYYMMDD}/
        stone_cartao_{date}_{merchant}_{timestamp}[_{tag}].xml

    Retorna None se backup desabilitado.
    """
    if not settings.STONE_XML_BACKUP_ENABLED:
        return None

    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    merchant = (merchant_id or settings.STONE_MERCHANT_ID or "merchant").strip()
    ymd = reference_date.strip()
    year = ymd[:4] if len(ymd) >= 4 else "0000"
    ts = datetime.now().strftime("%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"stone_cartao_{ymd}_{merchant}_{ts}{suffix}.xml"

    dest_dir = _backup_root() / "cartao" / year / ymd
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(raw)

    # Também mantém um "latest" fácil de achar no dia
    latest = dest_dir / f"stone_cartao_{ymd}_latest.xml"
    latest.write_bytes(raw)

    logger.info(
        "Backup XML cartão | date=%s | bytes=%s | path=%s",
        ymd,
        len(raw),
        dest,
    )
    return XmlBackupResult(path=dest, bytes_written=len(raw), reference_date=ymd)

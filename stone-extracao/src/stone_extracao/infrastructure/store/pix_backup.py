"""Backup físico do CSV PIX recebido no webhook (VM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class PixBackupResult:
    path: Path
    bytes_written: int
    reference_date: str
    conferencia_path: Path | None = None


def _backup_root() -> Path:
    configured = (settings.STONE_XML_BACKUP_DIR or "data/xml_backup").strip()
    root = Path(configured)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def pix_dir_for_date(iso_or_ymd: str) -> Path:
    raw = (iso_or_ymd or "").strip()
    if "-" in raw:
        ymd = raw.replace("-", "")[:8]
    else:
        ymd = raw[:8] if len(raw) >= 8 else datetime.now().strftime("%Y%m%d")
    year = ymd[:4] if len(ymd) >= 4 else "0000"
    return _backup_root() / "pix" / year / ymd


def save_pix_csv_backup(
    content: bytes | str,
    *,
    reference_date: str,
    source: str = "webhook",
) -> PixBackupResult | None:
    """
    Grava o CSV bruto do webhook/CSV manual.

      {STONE_XML_BACKUP_DIR}/pix/{YYYY}/{YYYYMMDD}/
        stone_pix_{date}_{timestamp}_{source}.csv
        stone_pix_{date}_latest.csv
    """
    if not settings.STONE_XML_BACKUP_ENABLED:
        return None

    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    ymd = (reference_date or "").replace("-", "")[:8] or datetime.now().strftime("%Y%m%d")
    ts = datetime.now().strftime("%H%M%S")
    safe_source = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (source or "pix"))[:40]
    dest_dir = pix_dir_for_date(ymd)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"stone_pix_{ymd}_{ts}_{safe_source}.csv"
    dest.write_bytes(raw)
    latest = dest_dir / f"stone_pix_{ymd}_latest.csv"
    latest.write_bytes(raw)
    logger.info(
        "Backup CSV PIX | date=%s | source=%s | bytes=%s | path=%s",
        ymd,
        source,
        len(raw),
        dest,
    )
    return PixBackupResult(path=dest, bytes_written=len(raw), reference_date=ymd)


def save_pix_conferencia(
    *,
    reference_date: str,
    payload: dict[str, Any],
) -> Path | None:
    if not settings.STONE_XML_BACKUP_ENABLED:
        return None
    ymd = (reference_date or "").replace("-", "")[:8] or datetime.now().strftime("%Y%m%d")
    dest_dir = pix_dir_for_date(ymd)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"stone_pix_{ymd}_conferencia.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Conferência PIX | date=%s | path=%s", ymd, dest)
    return dest


def ler_pix_conferencia(iso_or_ymd: str) -> dict[str, Any] | None:
    ymd = (iso_or_ymd or "").replace("-", "")[:8]
    dest = pix_dir_for_date(ymd) / f"stone_pix_{ymd}_conferencia.json"
    if not dest.is_file():
        return None
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Falha ao ler conferência PIX | path=%s", dest)
        return None
    if isinstance(data, dict):
        data["conferencia_path"] = str(dest)
        return data
    return None


def latest_pix_csv_path(iso_or_ymd: str) -> Path | None:
    ymd = (iso_or_ymd or "").replace("-", "")[:8]
    if len(ymd) != 8:
        return None
    dest = pix_dir_for_date(ymd) / f"stone_pix_{ymd}_latest.csv"
    return dest if dest.is_file() else None


def linhas_pix_backup(iso_or_ymd: str) -> dict[str, Any]:
    """Lê o CSV gravado na VM e monta as linhas da tela Movimentos Stone (sem publicar fila)."""
    from stone_extracao.infrastructure.parsers.pix_csv import parse_pix_csv_with_stats

    listing = listar_pix_backup(iso_or_ymd)
    ymd = str(listing.get("date") or "")
    path = latest_pix_csv_path(ymd)
    if path is None:
        return {**listing, "has_csv": False, "parsed_count": 0, "items": []}

    parsed = parse_pix_csv_with_stats(path.read_bytes())
    conf = listing.get("conferencia") if isinstance(listing.get("conferencia"), dict) else {}
    published_ids = {
        str(x).strip() for x in (conf.get("ids_publicados") or []) if str(x).strip()
    }
    iso = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}" if len(ymd) == 8 else None
    items: list[dict[str, Any]] = []
    for row in parsed.portal_rows:
        sid = str(row.get("id_stone") or "").strip()
        if not sid:
            continue
        skip = row.get("skip_reason")
        if published_ids:
            publicado = sid in published_ids
            motivo = None if publicado else (str(skip) if skip else "fora_piloto")
        else:
            publicado = skip is None
            motivo = str(skip) if skip else None
        amount = row.get("vl_transacao")
        items.append(
            {
                "origem": "pix",
                "id_stone": sid,
                "nr_serie_maquininha": row.get("nr_serie_maquininha"),
                "vl_transacao": str(amount) if amount is not None else None,
                "dt_movimentacao": row.get("dt_movimentacao"),
                "reference_date": row.get("reference_date") or iso,
                "status_origem": row.get("status_origem"),
                "operation": row.get("operation"),
                "publicado": "S" if publicado else "N",
                "ds_motivo": motivo,
                "source": str(conf.get("source") or "csv_backup")[:40],
            }
        )
    return {
        **listing,
        "has_csv": True,
        "csv_path": str(path),
        "parsed_count": len(items),
        "items": items,
    }


def listar_pix_backup(iso_or_ymd: str) -> dict[str, Any]:
    """Conferência + arquivos CSV gravados na VM para o dia."""
    ymd = (iso_or_ymd or "").replace("-", "")[:8]
    dest_dir = pix_dir_for_date(ymd) if ymd else None
    files: list[dict[str, Any]] = []
    if dest_dir is not None and dest_dir.is_dir():
        for path in sorted(dest_dir.iterdir()):
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "bytes": path.stat().st_size,
                        "path": str(path),
                    }
                )
    return {
        "date": ymd or None,
        "dir": str(dest_dir) if dest_dir is not None else None,
        "backup_enabled": settings.STONE_XML_BACKUP_ENABLED,
        "files": files,
        "conferencia": ler_pix_conferencia(ymd) if ymd else None,
    }

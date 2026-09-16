from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stone_extracao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

_PATH = Path(__file__).resolve().parent / "pix_webhook_inbox.json"
_MAX = 50


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def registrar_hit(
    *,
    method: str,
    path: str,
    client_ip: str | None,
    forwarded_for: str | None,
    content_type: str | None,
    body_len: int,
    body_preview: str,
    event_type: str | None = None,
    status: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Guarda os últimos POSTs/GETs no webhook (prova se a Stone bateu aqui)."""
    hit = {
        "at": _now_iso(),
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "forwarded_for": forwarded_for,
        "content_type": content_type,
        "body_len": body_len,
        "body_preview": (body_preview or "")[:400],
        "event_type": event_type,
        "status": status,
        "note": note,
    }
    data: dict[str, Any] = {"hits": []}
    try:
        if _PATH.is_file():
            raw = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("hits"), list):
                data = raw
    except Exception as exc:
        logger.warning("webhook inbox | falha ao ler: %s", exc)
    hits = list(data.get("hits") or [])
    hits.append(hit)
    data["hits"] = hits[-_MAX:]
    data["last_at"] = hit["at"]
    try:
        _PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.exception("webhook inbox | falha ao gravar")
    logger.info(
        "Webhook PIX hit | %s %s | ip=%s | fwd=%s | type=%s | bytes=%s | status=%s | preview=%s",
        method,
        path,
        client_ip or "-",
        (forwarded_for or "-")[:80],
        event_type or "-",
        body_len,
        status,
        (body_preview or "")[:160].replace("\n", " "),
    )
    return hit


def listar_hits(limit: int = 20) -> dict[str, Any]:
    data: dict[str, Any] = {"hits": []}
    try:
        if _PATH.is_file():
            raw = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
    except Exception as exc:
        logger.warning("webhook inbox | falha ao ler: %s", exc)
    hits = list(data.get("hits") or [])
    return {
        "count": len(hits),
        "last_at": data.get("last_at"),
        "hits": hits[-max(1, min(limit, _MAX)) :],
    }

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)

_STATE_PATH = Path(__file__).resolve().parent / "cron_pix_state.json"


def _default_enabled() -> bool:
    return bool(settings.PIX_CRON_ENABLED)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def carregar_estado() -> dict[str, Any]:
    data: dict[str, Any] = {
        "enabled": _default_enabled(),
        "last_run_at": None,
        "last_ok": None,
        "last_ok_at": None,
        "last_error_at": None,
        "last_error": None,
        "last_reference_date": None,
        "last_published": None,
        "last_slot": None,
        "last_status": None,
    }
    try:
        if _STATE_PATH.is_file():
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
    except Exception as exc:
        logger.warning("Falha ao ler estado do cron PIX: %s", exc)
    return data


def _salvar_estado(data: dict[str, Any]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def carregar_cron_pix_enabled() -> bool:
    return bool(carregar_estado().get("enabled", _default_enabled()))


def salvar_cron_pix_enabled(enabled: bool) -> bool:
    data = carregar_estado()
    data["enabled"] = bool(enabled)
    _salvar_estado(data)
    logger.info("Cron PIX D-1 | estado salvo | enabled=%s | path=%s", enabled, _STATE_PATH)
    return bool(enabled)


def registrar_resultado_cron_pix(
    *,
    ok: bool,
    reference_date: str,
    slot: str | None = None,
    published: int | None = None,
    status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    data = carregar_estado()
    now = _now_iso()
    data["last_run_at"] = now
    data["last_ok"] = bool(ok)
    data["last_reference_date"] = reference_date
    data["last_slot"] = slot
    data["last_published"] = published
    data["last_status"] = status
    if ok:
        data["last_ok_at"] = now
        data["last_error"] = None
        data["last_error_at"] = None
    else:
        data["last_error_at"] = now
        data["last_error"] = (error or "falha desconhecida")[:500]
    _salvar_estado(data)
    return data

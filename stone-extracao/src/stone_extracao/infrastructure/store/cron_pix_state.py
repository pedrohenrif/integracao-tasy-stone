from __future__ import annotations

import json
from pathlib import Path

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)

_STATE_PATH = Path(__file__).resolve().parent / "cron_pix_state.json"


def _default_enabled() -> bool:
    return bool(settings.PIX_CRON_ENABLED)


def carregar_cron_pix_enabled() -> bool:
    """Estado persistido do painel; fallback para PIX_CRON_ENABLED do .env."""
    try:
        if _STATE_PATH.is_file():
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if "enabled" in data:
                return bool(data["enabled"])
    except Exception as exc:
        logger.warning("Falha ao ler estado do cron PIX: %s", exc)
    return _default_enabled()


def salvar_cron_pix_enabled(enabled: bool) -> bool:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"enabled": bool(enabled)}
    _STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Cron PIX D-1 | estado salvo | enabled=%s | path=%s", enabled, _STATE_PATH)
    return bool(enabled)

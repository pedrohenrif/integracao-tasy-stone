from __future__ import annotations

from typing import Any

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def enviar_movimentos_stone(items: list[dict[str, Any]]) -> None:
    """Espelha o CSV/XML no portal (tasy-insercao). Sem token, só loga."""
    if not items:
        return
    base = (settings.PORTAL_BASE_URL or "").rstrip("/")
    token = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not base or not token:
        logger.debug("Movimentos portal ignorados (PORTAL_BASE_URL/TOKEN vazios) | n=%s", len(items))
        return
    url = f"{base}/interno/movimentos-stone"
    batch = 400
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for i in range(0, len(items), batch):
                chunk = items[i : i + batch]
                resp = await client.post(
                    url,
                    headers={"X-Internal-Token": token},
                    json={"items": chunk},
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "Movimentos portal HTTP %s | n=%s | %s",
                        resp.status_code,
                        len(chunk),
                        resp.text[:200],
                    )
    except Exception as exc:
        logger.warning("Movimentos portal falhou | n=%s | %s", len(items), exc)

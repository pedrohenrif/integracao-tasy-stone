from __future__ import annotations

from typing import Any

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


async def notificar_auditoria_portal(
    *,
    acao: str,
    obs: str | None = None,
    depois: dict[str, Any] | None = None,
) -> None:
    """
    Envia evento de sistema (scheduler) para portal_acao_log no tasy-insercao.
    Se PORTAL_BASE_URL / token não estiverem configurados, só loga e segue.
    """
    base = (settings.PORTAL_BASE_URL or "").rstrip("/")
    token = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not base or not token:
        logger.debug(
            "Auditoria portal ignorada (PORTAL_BASE_URL/TOKEN vazios) | acao=%s",
            acao,
        )
        return
    url = f"{base}/api/audit/sistema"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url,
                headers={"X-Internal-Token": token},
                json={
                    "acao": acao,
                    "obs": (obs or "")[:500] or None,
                    "depois": depois,
                },
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Auditoria portal HTTP %s | acao=%s | %s",
                    resp.status_code,
                    acao,
                    resp.text[:200],
                )
    except Exception as exc:
        logger.warning("Auditoria portal falhou | acao=%s | %s", acao, exc)

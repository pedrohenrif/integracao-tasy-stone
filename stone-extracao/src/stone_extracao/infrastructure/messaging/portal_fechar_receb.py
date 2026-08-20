from __future__ import annotations

from typing import Any

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)


def _ymd_to_iso(reference_date: str) -> str:
    """YYYYMMDD → YYYY-MM-DD."""
    ymd = (reference_date or "").strip()
    if len(ymd) == 10 and ymd[4] == "-":
        return ymd
    if len(ymd) != 8 or not ymd.isdigit():
        raise ValueError(f"reference_date inválida: {reference_date!r}")
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"


async def notificar_fechar_recebimentos(
    *,
    reference_date: str,
    slot: str | None = None,
) -> dict[str, Any] | None:
    """
    Chama tasy-insercao para FECHAR recebimentos Stone abertos do dia (D-1).

    Exige PORTAL_BASE_URL + PORTAL_INTERNAL_TOKEN. Se FECHAR_RECEB_ENABLED=false,
    só loga e retorna None.
    """
    if not settings.FECHAR_RECEB_ENABLED:
        logger.debug(
            "Fechar recebimentos ignorado (FECHAR_RECEB_ENABLED=false) | date=%s",
            reference_date,
        )
        return None

    base = (settings.PORTAL_BASE_URL or "").rstrip("/")
    token = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not base or not token:
        logger.warning(
            "Fechar recebimentos ignorado (PORTAL_BASE_URL/TOKEN vazios) | date=%s",
            reference_date,
        )
        return None

    try:
        date_iso = _ymd_to_iso(reference_date)
    except ValueError as exc:
        logger.warning("Fechar recebimentos | %s", exc)
        return None

    url = f"{base}/interno/tesouraria/fechar-recebimentos-abertos"
    params: dict[str, Any] = {"date": date_iso}
    logger.info(
        "Fechar recebimentos | chamando portal | date=%s | slot=%s | url=%s",
        date_iso,
        slot,
        url,
    )
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                params=params,
                headers={"X-Internal-Token": token},
            )
            body: dict[str, Any] | None
            try:
                body = resp.json() if resp.content else None
            except Exception:
                body = None
            if resp.status_code >= 400:
                logger.warning(
                    "Fechar recebimentos HTTP %s | date=%s | %s",
                    resp.status_code,
                    date_iso,
                    (resp.text or "")[:300],
                )
                return {
                    "ok": False,
                    "http_status": resp.status_code,
                    "date": date_iso,
                    "body": body,
                }
            logger.info(
                "Fechar recebimentos ok | date=%s | fechados=%s | falhas=%s",
                date_iso,
                (body or {}).get("fechados"),
                (body or {}).get("falhas"),
            )
            return body if isinstance(body, dict) else {"ok": True, "date": date_iso}
    except Exception as exc:
        logger.warning("Fechar recebimentos falhou | date=%s | %s", date_iso, exc)
        return {"ok": False, "date": date_iso, "erro": str(exc)[:300]}

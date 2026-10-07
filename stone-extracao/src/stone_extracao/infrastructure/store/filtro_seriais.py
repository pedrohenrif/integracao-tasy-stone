"""Filtro de seriais na publicação: cadastro ativo no portal (ie_status=A)."""

from __future__ import annotations

import time

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings

logger = get_logger(__name__)

_CACHE_TTL_SEC = 60.0
_cache_at: float = 0.0
_cache_seriais: set[str] | None = None


def parse_seriais(raw: str | None) -> set[str]:
    return {p.strip().upper() for p in (raw or "").split(",") if p.strip()}


def reset_cache() -> None:
    global _cache_at, _cache_seriais
    _cache_at = 0.0
    _cache_seriais = None


async def fetch_seriais_ativos() -> set[str] | None:
    """
    Seriais ie_status=A no portal. None = não conseguiu obter lista
    (publica todos; o consumer ainda ignora inativas).
    """
    global _cache_at, _cache_seriais
    now = time.monotonic()
    if _cache_seriais is not None and (now - _cache_at) < _CACHE_TTL_SEC:
        return set(_cache_seriais)

    base = (settings.PORTAL_BASE_URL or "").rstrip("/")
    token = (settings.PORTAL_INTERNAL_TOKEN or "").strip()
    if not base or not token:
        logger.warning(
            "Seriais ativos: PORTAL_BASE_URL/TOKEN vazios — sem filtro na extração"
        )
        if _cache_seriais is not None:
            return set(_cache_seriais)
        return None

    url = f"{base}/interno/seriais-ativos"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers={"X-Internal-Token": token})
        if resp.status_code >= 400:
            logger.warning(
                "Seriais ativos HTTP %s | %s",
                resp.status_code,
                (resp.text or "")[:200],
            )
            if _cache_seriais is not None:
                return set(_cache_seriais)
            return None
        data = resp.json() if resp.content else {}
        seriais = {
            str(s).strip().upper()
            for s in (data.get("seriais") or [])
            if str(s).strip()
        }
        _cache_seriais = seriais
        _cache_at = now
        logger.info("Seriais ativos do cadastro | n=%s", len(seriais))
        return set(seriais)
    except Exception as exc:
        logger.warning("Seriais ativos falhou | %s", exc)
        if _cache_seriais is not None:
            return set(_cache_seriais)
        return None


async def resolve_terminals(explicit: str | set[str] | None = None) -> set[str] | None:
    """
    Prioridade: parâmetro explícito (API ?terminal=) > cadastro ativo no portal.
    None = sem filtro (publica todos). set vazio = não publica ninguém.
    """
    if isinstance(explicit, str):
        wanted = parse_seriais(explicit)
        return wanted or None
    if isinstance(explicit, set):
        wanted = {str(t).strip().upper() for t in explicit if t and str(t).strip()}
        return wanted or None
    return await fetch_seriais_ativos()

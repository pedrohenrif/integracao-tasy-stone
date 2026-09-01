"""Filtro opcional de seriais na publicação (piloto)."""

from __future__ import annotations

from stone_extracao.infrastructure.config.settings import settings


def parse_seriais(raw: str | None) -> set[str]:
    return {p.strip() for p in (raw or "").split(",") if p.strip()}


def publicar_somente_seriais() -> set[str]:
    return parse_seriais(settings.PUBLICAR_SOMENTE_SERIAIS)


def resolve_terminals(explicit: str | set[str] | None = None) -> set[str] | None:
    """
    Prioridade: parâmetro explícito (API) > PUBLICAR_SOMENTE_SERIAIS no .env.
    None = sem filtro (publica todos).
    """
    if isinstance(explicit, str):
        wanted = parse_seriais(explicit)
        return wanted or None
    if isinstance(explicit, set):
        wanted = {t.strip() for t in explicit if t and str(t).strip()}
        return wanted or None
    env = publicar_somente_seriais()
    return env or None

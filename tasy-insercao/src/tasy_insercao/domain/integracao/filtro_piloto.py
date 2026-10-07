"""Regras de cadastro: sem maquininha ativa não grava Oracle (salvo policy insert)."""

from __future__ import annotations

from tasy_insercao.infrastructure.config.settings import settings


def parse_csv_ints(raw: str) -> frozenset[int]:
    out: set[int] = set()
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            continue
    return frozenset(out)


def parse_csv_strs(raw: str) -> frozenset[str]:
    return frozenset(p.strip() for p in (raw or "").split(",") if p.strip())


def sem_caixa_policy() -> str:
    """ignore (default) | insert (legado Sem Tesouraria no Oracle)."""
    raw = (settings.SEM_CAIXA_POLICY or "ignore").strip().lower()
    return raw if raw in ("ignore", "insert") else "ignore"


def motivo_ignorar(*, serial: str, cd_caixa: int | None) -> str | None:
    """
    Allowlist de .env foi removida: só o cadastro (ie_status=A) decide.
    Sempre None — inativa/não cadastrada cai em SEM_CAIXA_POLICY.
    """
    return None

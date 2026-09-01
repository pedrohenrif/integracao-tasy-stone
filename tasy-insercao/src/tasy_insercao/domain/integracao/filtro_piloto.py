"""Filtro de piloto: só integra seriais/caixas permitidos; sem caixa não grava Oracle."""

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


def integrar_somente_caixas() -> frozenset[int]:
    return parse_csv_ints(settings.INTEGRAR_SOMENTE_CAIXAS)


def integrar_somente_seriais() -> frozenset[str]:
    return parse_csv_strs(settings.INTEGRAR_SOMENTE_SERIAIS)


def sem_caixa_policy() -> str:
    """ignore (default) | insert (legado Sem Tesouraria no Oracle)."""
    raw = (settings.SEM_CAIXA_POLICY or "ignore").strip().lower()
    return raw if raw in ("ignore", "insert") else "ignore"


def motivo_ignorar(*, serial: str, cd_caixa: int | None) -> str | None:
    """
    Retorna motivo para status IGNORADO, ou None se pode seguir integração.
    Allowlist vazia = sem restrição de piloto (só cadastro/policy de sem-caixa).
    """
    serial_n = (serial or "").strip()
    seriais = integrar_somente_seriais()
    caixas = integrar_somente_caixas()

    if seriais and serial_n not in seriais:
        return (
            f"serial fora do piloto (INTEGRAR_SOMENTE_SERIAIS="
            f"{','.join(sorted(seriais))})"
        )

    if caixas and cd_caixa is not None and int(cd_caixa) not in caixas:
        return (
            f"caixa {cd_caixa} fora do piloto (INTEGRAR_SOMENTE_CAIXAS="
            f"{','.join(str(c) for c in sorted(caixas))})"
        )

    return None

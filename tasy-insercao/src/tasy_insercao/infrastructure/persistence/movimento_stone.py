"""Espelho das transações Stone (CSV/XML) para o portal — fora do registro_maquininha."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from psycopg.rows import dict_row

from tasy_insercao.infrastructure.config.settings import settings


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _as_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw.split("+")[0])
    except ValueError:
        return None


def _clip(value: Any, n: int) -> str | None:
    """None/vazio não pode ir para slice (`None[:240]` quebra a tela Movimentos)."""
    text = str(value or "").strip()
    return text[:n] if text else None


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    if len(raw) >= 8 and raw[:8].isdigit():
        try:
            return datetime.strptime(raw[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def item_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Monta o bind do upsert. Publicado sem motivo (caso normal) não pode estourar."""
    id_stone = str(raw.get("id_stone") or "").strip()
    origem = str(raw.get("origem") or "").strip().lower()[:10]
    if not id_stone or origem not in ("pix", "cartao"):
        return None
    dt_mov = _as_dt(raw.get("dt_movimentacao"))
    ref_date = _as_date(raw.get("reference_date"))
    if ref_date is None and dt_mov is not None:
        ref_date = dt_mov.date()
    publicado = "S" if str(raw.get("publicado") or "").upper()[:1] in ("S", "1", "T") else "N"
    return {
        "origem": origem,
        "id_stone": id_stone[:80],
        "serial": _clip(raw.get("nr_serie_maquininha"), 64),
        "vl": _as_decimal(raw.get("vl_transacao")),
        "dt": dt_mov,
        "ref": ref_date,
        "status": _clip(raw.get("status_origem"), 40),
        "operation": _clip(raw.get("operation"), 40),
        "publicado": publicado,
        "motivo": _clip(raw.get("ds_motivo"), 240),
        "source": _clip(raw.get("source"), 40),
    }


def upsert_movimentos(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    sql = """
        INSERT INTO movimento_stone (
            origem, id_stone, nr_serie_maquininha, vl_transacao, dt_movimentacao,
            reference_date, status_origem, operation, publicado, ds_motivo, source
        ) VALUES (
            %(origem)s, %(id_stone)s, %(serial)s, %(vl)s, %(dt)s,
            %(ref)s, %(status)s, %(operation)s, %(publicado)s, %(motivo)s, %(source)s
        )
        ON CONFLICT (origem, id_stone) DO UPDATE SET
            nr_serie_maquininha = EXCLUDED.nr_serie_maquininha,
            vl_transacao = COALESCE(EXCLUDED.vl_transacao, movimento_stone.vl_transacao),
            dt_movimentacao = COALESCE(EXCLUDED.dt_movimentacao, movimento_stone.dt_movimentacao),
            reference_date = COALESCE(EXCLUDED.reference_date, movimento_stone.reference_date),
            status_origem = EXCLUDED.status_origem,
            operation = EXCLUDED.operation,
            publicado = EXCLUDED.publicado,
            ds_motivo = EXCLUDED.ds_motivo,
            source = EXCLUDED.source,
            dt_atualizacao = NOW()
    """
    count = 0
    with _connect() as conn, conn.cursor() as cur:
        for raw in items:
            params = item_params(raw)
            if params is None:
                continue
            cur.execute(sql, params)
            count += 1
        conn.commit()
    return count


def listar_movimentos(
    *,
    data_de: date | None = None,
    data_ate: date | None = None,
    origem: str | None = None,
    nr_serie: str | None = None,
    publicado: str | None = None,
    id_stone: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    clauses = ["TRUE"]
    params: dict[str, Any] = {"limit": min(max(limit, 1), 2000), "offset": max(offset, 0)}
    if data_de:
        clauses.append("m.reference_date >= %(data_de)s")
        params["data_de"] = data_de
    if data_ate:
        clauses.append("m.reference_date <= %(data_ate)s")
        params["data_ate"] = data_ate
    if origem in ("pix", "cartao"):
        clauses.append("m.origem = %(origem)s")
        params["origem"] = origem
    if nr_serie:
        clauses.append("m.nr_serie_maquininha ILIKE %(serie)s")
        params["serie"] = f"%{nr_serie.strip()}%"
    if publicado in ("S", "N"):
        clauses.append("m.publicado = %(pub)s")
        params["pub"] = publicado
    if id_stone:
        clauses.append("m.id_stone ILIKE %(id_stone)s")
        params["id_stone"] = f"%{id_stone.strip()}%"
    where = " AND ".join(clauses)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE m.publicado = 'S') AS publicados,
                COUNT(*) FILTER (WHERE m.publicado = 'N') AS nao_publicados,
                COALESCE(SUM(m.vl_transacao), 0) AS soma_valor
            FROM movimento_stone m
            WHERE {where}
            """,
            params,
        )
        resumo = cur.fetchone() or {}
        cur.execute(
            f"""
            SELECT
                m.nr_sequencia, m.origem, m.id_stone, m.nr_serie_maquininha,
                m.vl_transacao, m.dt_movimentacao, m.reference_date,
                m.status_origem, m.operation, m.publicado, m.ds_motivo, m.source
            FROM movimento_stone m
            WHERE {where}
            ORDER BY m.dt_movimentacao DESC NULLS LAST, m.nr_sequencia DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = list(cur.fetchall())
    return {"resumo": resumo, "items": rows}

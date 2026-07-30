from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from tasy_insercao.infrastructure.config.settings import settings


@dataclass
class FiltrosPainel:
    data_de: date | None = None
    data_ate: date | None = None
    cd_caixa: int | None = None
    cd_status: int | None = None
    cd_tipo_transacao: str | None = None
    id_stone: str | None = None
    nr_serie: str | None = None
    cd_autorizacao: str | None = None
    cd_bandeira: str | None = None
    vl_min: Decimal | None = None
    vl_max: Decimal | None = None
    obs: str | None = None
    limit: int = 200
    offset: int = 0


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado no .env")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def _where(f: FiltrosPainel) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = ["1=1"]
    params: dict[str, Any] = {}

    if f.data_de is not None:
        clauses.append("r.dt_movimentacao >= %(data_de)s")
        params["data_de"] = datetime.combine(f.data_de, datetime.min.time())
    if f.data_ate is not None:
        clauses.append("r.dt_movimentacao < %(data_ate)s + INTERVAL '1 day'")
        params["data_ate"] = f.data_ate
    if f.cd_caixa is not None:
        clauses.append("r.cd_caixa = %(cd_caixa)s")
        params["cd_caixa"] = f.cd_caixa
    if f.cd_status is not None:
        clauses.append("r.cd_status = %(cd_status)s")
        params["cd_status"] = f.cd_status
    if f.cd_tipo_transacao:
        tipo = f.cd_tipo_transacao.strip().lower()
        if tipo == "pix":
            clauses.append(
                "(LOWER(COALESCE(r.cd_tipo_transacao, '')) = 'pix' "
                "OR LOWER(COALESCE(r.ds_obs_processo, '')) LIKE '%pix%')"
            )
        else:
            clauses.append("LOWER(COALESCE(r.cd_tipo_transacao, '')) = %(tipo)s")
            params["tipo"] = tipo
    if f.id_stone:
        clauses.append("r.id_stone ILIKE %(id_stone)s")
        params["id_stone"] = f"%{f.id_stone.strip()}%"
    if f.nr_serie:
        clauses.append("r.nr_serie_maquininha ILIKE %(nr_serie)s")
        params["nr_serie"] = f"%{f.nr_serie.strip()}%"
    if f.cd_autorizacao:
        clauses.append("r.cd_autorizacao ILIKE %(cd_autorizacao)s")
        params["cd_autorizacao"] = f"%{f.cd_autorizacao.strip()}%"
    if f.cd_bandeira:
        clauses.append("LOWER(COALESCE(r.cd_bandeira, '')) LIKE %(cd_bandeira)s")
        params["cd_bandeira"] = f"%{f.cd_bandeira.strip().lower()}%"
    if f.vl_min is not None:
        clauses.append("r.vl_transacao >= %(vl_min)s")
        params["vl_min"] = f.vl_min
    if f.vl_max is not None:
        clauses.append("r.vl_transacao <= %(vl_max)s")
        params["vl_max"] = f.vl_max
    if f.obs:
        clauses.append("r.ds_obs_processo ILIKE %(obs)s")
        params["obs"] = f"%{f.obs.strip()}%"

    return " AND ".join(clauses), params


def listar_caixas() -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT cd_caixa, ds_caixa
            FROM caixas_tasy
            ORDER BY ds_caixa
            """
        )
        return list(cur.fetchall())


def resumo(f: FiltrosPainel) -> dict[str, Any]:
    where_sql, params = _where(f)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE r.cd_status = 5) AS ok,
                COUNT(*) FILTER (WHERE r.cd_status = 6) AS retry,
                COUNT(*) FILTER (WHERE r.cd_status = 7) AS dlq,
                COUNT(*) FILTER (WHERE r.cd_status = 8) AS sem_tesouraria,
                COUNT(*) FILTER (WHERE r.cd_status IN (1, 2)) AS pendente,
                COALESCE(SUM(r.vl_transacao), 0) AS soma_valor,
                COALESCE(SUM(r.vl_transacao) FILTER (WHERE r.cd_status = 5), 0) AS soma_ok
            FROM registro_maquininha r
            WHERE {where_sql}
            """,
            params,
        )
        row = cur.fetchone() or {}
        cur.execute(
            f"""
            SELECT r.cd_status, COUNT(*) AS qtd
            FROM registro_maquininha r
            WHERE {where_sql}
            GROUP BY r.cd_status
            ORDER BY r.cd_status
            """,
            params,
        )
        por_status = list(cur.fetchall())
        cur.execute(
            f"""
            SELECT
                COALESCE(r.cd_caixa, 0) AS cd_caixa,
                COALESCE(c.ds_caixa, '(sem caixa)') AS ds_caixa,
                COUNT(*) AS qtd,
                COALESCE(SUM(r.vl_transacao), 0) AS total
            FROM registro_maquininha r
            LEFT JOIN caixas_tasy c ON c.cd_caixa = r.cd_caixa
            WHERE {where_sql}
            GROUP BY 1, 2
            ORDER BY qtd DESC
            LIMIT 30
            """,
            params,
        )
        por_caixa = list(cur.fetchall())
    return {"totais": row, "por_status": por_status, "por_caixa": por_caixa}


_REGISTRO_COLS = """
    r.nr_sequencia,
    r.id_stone,
    r.nr_serie_maquininha,
    r.cd_caixa,
    c.ds_caixa,
    r.dt_movimentacao,
    r.cd_autorizacao,
    r.vl_transacao,
    r.cd_tipo_transacao,
    r.cd_bandeira,
    r.qt_parcelas,
    r.ie_transacao_parcelada,
    r.cd_status,
    r.ds_obs_processo,
    r.dt_inclusao,
    r.dt_atualizacao
"""


def listar_registros(f: FiltrosPainel) -> list[dict[str, Any]]:
    where_sql, params = _where(f)
    limit = max(1, min(f.limit, 1000))
    offset = max(0, f.offset)
    params = {**params, "limit": limit, "offset": offset}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_REGISTRO_COLS}
            FROM registro_maquininha r
            LEFT JOIN caixas_tasy c ON c.cd_caixa = r.cd_caixa
            WHERE {where_sql}
            ORDER BY r.dt_movimentacao DESC, r.nr_sequencia DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        return list(cur.fetchall())


def listar_registros_por_ids(nr_sequencias: list[int]) -> list[dict[str, Any]]:
    if not nr_sequencias:
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_REGISTRO_COLS}
            FROM registro_maquininha r
            LEFT JOIN caixas_tasy c ON c.cd_caixa = r.cd_caixa
            WHERE r.nr_sequencia = ANY(%(ids)s)
            ORDER BY r.nr_sequencia
            """,
            {"ids": nr_sequencias},
        )
        return list(cur.fetchall())


def atualizar_status_registro(nr_sequencia: int, cd_status: int, obs: str) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE registro_maquininha
            SET cd_status = %(cd_status)s,
                ds_obs_processo = %(obs)s
            WHERE nr_sequencia = %(nr_sequencia)s
            """,
            {
                "cd_status": cd_status,
                "obs": (obs or "")[:500],
                "nr_sequencia": nr_sequencia,
            },
        )
        conn.commit()


def atualizar_registro_reprocesso(
    nr_sequencia: int,
    *,
    nr_serie_maquininha: str | None = None,
    cd_caixa: int | None = None,
    cd_status: int | None = None,
    obs: str | None = None,
) -> dict[str, Any] | None:
    """Atualiza serial/caixa/status do registro e devolve a linha atualizada."""
    sets: list[str] = []
    params: dict[str, Any] = {"nr_sequencia": nr_sequencia}
    if nr_serie_maquininha is not None:
        sets.append("nr_serie_maquininha = %(nr_serie_maquininha)s")
        params["nr_serie_maquininha"] = nr_serie_maquininha.strip()
    if cd_caixa is not None:
        sets.append("cd_caixa = %(cd_caixa)s")
        params["cd_caixa"] = cd_caixa
    if cd_status is not None:
        sets.append("cd_status = %(cd_status)s")
        params["cd_status"] = cd_status
    if obs is not None:
        sets.append("ds_obs_processo = %(obs)s")
        params["obs"] = obs[:500]

    if not sets:
        rows = listar_registros_por_ids([nr_sequencia])
        return rows[0] if rows else None

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE registro_maquininha
            SET {", ".join(sets)}
            WHERE nr_sequencia = %(nr_sequencia)s
            """,
            params,
        )
        conn.commit()
    rows = listar_registros_por_ids([nr_sequencia])
    return rows[0] if rows else None

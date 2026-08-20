from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tasy_insercao.infrastructure.config.settings import settings


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def registrar_acao_log(
    *,
    user_id: int | None,
    login: str,
    acao: str,
    nr_seq_registro: int | None = None,
    id_stone: str | None = None,
    antes: dict[str, Any] | None = None,
    depois: dict[str, Any] | None = None,
    obs: str | None = None,
) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO portal_acao_log (
                nr_seq_usuario, ds_login, ds_acao, nr_seq_registro,
                id_stone, ds_antes, ds_depois, ds_obs
            ) VALUES (
                %(user_id)s, %(login)s, %(acao)s, %(nr_seq_registro)s,
                %(id_stone)s, %(antes)s, %(depois)s, %(obs)s
            )
            """,
            {
                "user_id": user_id,
                "login": (login or "")[:80],
                "acao": (acao or "")[:80],
                "nr_seq_registro": nr_seq_registro,
                "id_stone": (id_stone or "")[:80] or None,
                "antes": Jsonb(antes) if antes is not None else None,
                "depois": Jsonb(depois) if depois is not None else None,
                "obs": (obs or "")[:500] or None,
            },
        )
        conn.commit()


def _serialize_row(r: dict[str, Any]) -> dict[str, Any]:
    item = dict(r)
    for key in ("ds_antes", "ds_depois"):
        val = item.get(key)
        if isinstance(val, (bytes, str)):
            try:
                item[key] = json.loads(val) if isinstance(val, (bytes, bytearray)) else json.loads(val)
            except (TypeError, json.JSONDecodeError):
                pass
    if hasattr(item.get("dt_evento"), "isoformat"):
        item["dt_evento"] = item["dt_evento"].isoformat(sep=" ", timespec="seconds")
    return item


def listar_acao_logs(
    limit: int = 50,
    offset: int = 0,
    *,
    acao: str | None = None,
    login: str | None = None,
    id_stone: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> dict[str, Any]:
    clauses = ["1=1"]
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }
    if acao:
        clauses.append("l.ds_acao ILIKE %(acao)s")
        params["acao"] = f"%{acao.strip()}%"
    if login:
        clauses.append("l.ds_login ILIKE %(login)s")
        params["login"] = f"%{login.strip()}%"
    if id_stone:
        clauses.append("l.id_stone ILIKE %(id_stone)s")
        params["id_stone"] = f"%{id_stone.strip()}%"
    if data_de is not None:
        clauses.append("l.dt_evento >= %(data_de)s")
        params["data_de"] = datetime.combine(data_de, datetime.min.time())
    if data_ate is not None:
        clauses.append("l.dt_evento < %(data_ate)s + INTERVAL '1 day'")
        params["data_ate"] = data_ate

    where_sql = " AND ".join(clauses)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS total FROM portal_acao_log l WHERE {where_sql}",
            params,
        )
        total = int((cur.fetchone() or {}).get("total") or 0)
        cur.execute(
            f"""
            SELECT
                l.nr_sequencia,
                l.nr_seq_usuario,
                l.ds_login,
                l.ds_acao,
                l.nr_seq_registro,
                l.id_stone,
                l.ds_antes,
                l.ds_depois,
                l.ds_obs,
                l.dt_evento,
                u.ds_nome
            FROM portal_acao_log l
            LEFT JOIN portal_usuario u ON u.nr_sequencia = l.nr_seq_usuario
            WHERE {where_sql}
            ORDER BY l.dt_evento DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = [_serialize_row(dict(r)) for r in cur.fetchall()]

    return {
        "items": rows,
        "total": total,
        "limit": params["limit"],
        "offset": params["offset"],
    }

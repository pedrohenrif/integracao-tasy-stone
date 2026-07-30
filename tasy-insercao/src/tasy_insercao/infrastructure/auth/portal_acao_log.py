from __future__ import annotations

import json
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


def listar_acao_logs(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
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
            ORDER BY l.dt_evento DESC
            LIMIT %(limit)s
            """,
            {"limit": max(1, min(limit, 500))},
        )
        rows = list(cur.fetchall())

    # serializa JSONB / datetime para API
    out: list[dict[str, Any]] = []
    for r in rows:
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
        out.append(item)
    return out

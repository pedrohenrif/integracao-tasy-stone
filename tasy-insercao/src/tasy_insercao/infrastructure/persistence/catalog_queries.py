from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from tasy_insercao.infrastructure.config.settings import settings


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def listar_maquininhas() -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.nr_sequencia,
                m.nr_serie_maquininha,
                m.cd_caixa,
                c.ds_caixa,
                m.ds_maquininha,
                m.ie_status,
                m.cd_transacao_financeira,
                m.dt_registro
            FROM maquininha_stone m
            LEFT JOIN caixas_tasy c ON c.cd_caixa = m.cd_caixa
            ORDER BY m.ie_status, m.nr_serie_maquininha
            """
        )
        return list(cur.fetchall())


def upsert_maquininha(
    *,
    nr_serie_maquininha: str,
    cd_caixa: int,
    cd_transacao_financeira: int,
    ds_maquininha: str | None,
    ie_status: str,
) -> dict[str, Any]:
    serial = nr_serie_maquininha.strip()
    status = (ie_status or "A").strip().upper()[:1]
    if status not in ("A", "I"):
        status = "A"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO maquininha_stone (
                nr_serie_maquininha, cd_caixa, ds_maquininha,
                ie_status, cd_transacao_financeira
            ) VALUES (
                %(serial)s, %(caixa)s, %(nome)s, %(status)s, %(trans)s
            )
            ON CONFLICT (nr_serie_maquininha) DO UPDATE SET
                cd_caixa = EXCLUDED.cd_caixa,
                ds_maquininha = EXCLUDED.ds_maquininha,
                ie_status = EXCLUDED.ie_status,
                cd_transacao_financeira = EXCLUDED.cd_transacao_financeira
            RETURNING
                nr_sequencia, nr_serie_maquininha, cd_caixa, ds_maquininha,
                ie_status, cd_transacao_financeira, dt_registro
            """,
            {
                "serial": serial,
                "caixa": cd_caixa,
                "nome": (ds_maquininha or "").strip() or None,
                "status": status,
                "trans": cd_transacao_financeira,
            },
        )
        row = cur.fetchone()
        conn.commit()
        return row or {}


def listar_mapeamentos() -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.nr_sequencia,
                m.cd_cartao_bandeira_tasy,
                m.cd_tipo_transacao,
                t.ds_tipo_transacao,
                m.cd_bandeira,
                b.ds_bandeira
            FROM mapeamento_transacoes_tasy m
            JOIN tipos_transacoes t ON t.cd_tipo_transacao = m.cd_tipo_transacao
            LEFT JOIN bandeiras b ON b.cd_bandeira = m.cd_bandeira
            ORDER BY m.cd_tipo_transacao, m.cd_bandeira NULLS FIRST
            """
        )
        return list(cur.fetchall())


def criar_mapeamento(
    *,
    cd_cartao_bandeira_tasy: int,
    cd_tipo_transacao: int,
    cd_bandeira: int | None,
) -> dict[str, Any]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mapeamento_transacoes_tasy (
                cd_cartao_bandeira_tasy, cd_tipo_transacao, cd_bandeira
            ) VALUES (%(tasy)s, %(tipo)s, %(bandeira)s)
            RETURNING nr_sequencia, cd_cartao_bandeira_tasy, cd_tipo_transacao, cd_bandeira
            """,
            {
                "tasy": cd_cartao_bandeira_tasy,
                "tipo": cd_tipo_transacao,
                "bandeira": cd_bandeira,
            },
        )
        row = cur.fetchone()
        conn.commit()
        return row or {}


def atualizar_mapeamento(
    nr_sequencia: int,
    *,
    cd_cartao_bandeira_tasy: int,
    cd_tipo_transacao: int,
    cd_bandeira: int | None,
) -> dict[str, Any] | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE mapeamento_transacoes_tasy
            SET
                cd_cartao_bandeira_tasy = %(tasy)s,
                cd_tipo_transacao = %(tipo)s,
                cd_bandeira = %(bandeira)s
            WHERE nr_sequencia = %(id)s
            RETURNING nr_sequencia, cd_cartao_bandeira_tasy, cd_tipo_transacao, cd_bandeira
            """,
            {
                "id": nr_sequencia,
                "tasy": cd_cartao_bandeira_tasy,
                "tipo": cd_tipo_transacao,
                "bandeira": cd_bandeira,
            },
        )
        row = cur.fetchone()
        conn.commit()
        return row


def listar_tipos() -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT cd_tipo_transacao, ds_tipo_transacao FROM tipos_transacoes ORDER BY 1"
        )
        return list(cur.fetchall())


def listar_bandeiras() -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT cd_bandeira, ds_bandeira FROM bandeiras ORDER BY 1")
        return list(cur.fetchall())


def upsert_bandeira(cd_bandeira: int, ds_bandeira: str) -> dict[str, Any]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bandeiras (cd_bandeira, ds_bandeira)
            VALUES (%(id)s, %(nome)s)
            ON CONFLICT (cd_bandeira) DO UPDATE SET ds_bandeira = EXCLUDED.ds_bandeira
            RETURNING cd_bandeira, ds_bandeira
            """,
            {"id": cd_bandeira, "nome": ds_bandeira.strip()},
        )
        row = cur.fetchone()
        conn.commit()
        return row or {}


def seriais_com_erro_cadastro() -> list[str]:
    """Seriais em DLQ ou Sem Tesouraria (faltando cadastro / amarrar no Tasy)."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT r.nr_serie_maquininha
            FROM registro_maquininha r
            WHERE (
                (r.cd_status = 7 AND r.ds_obs_processo ILIKE '%%não cadastrada%%')
                OR (r.cd_status = 8)
                OR (r.ds_obs_processo ILIKE '%%SEM_TESOURARIA%%')
              )
            ORDER BY 1
            """
        )
        return [r["nr_serie_maquininha"] for r in cur.fetchall()]

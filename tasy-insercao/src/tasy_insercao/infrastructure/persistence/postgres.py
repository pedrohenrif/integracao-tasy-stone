from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import psycopg
from psycopg.rows import tuple_row

from tasy_insercao.domain.integracao.models import TransacaoCartao
from tasy_insercao.domain.integracao.policies import (
    map_bandeira_para_local,
    map_stone_brand,
    map_tipo_para_local,
    to_float_money,
)
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.queries import postgre_queries as pg

logger = get_logger(__name__)


class PostgresDB:
    def __init__(self) -> None:
        self._conn: psycopg.Connection | None = None

    def connect(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            if not settings.POSTGRES_DB:
                raise RuntimeError("POSTGRES_DB não configurado")
            self._conn = psycopg.connect(settings.postgres_url, row_factory=tuple_row)
            logger.info("Conectando Postgres | %s", settings.POSTGRES_HOST)
        return self._conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def reset(self) -> None:
        self.close()

    @contextmanager
    def cursor(self) -> Generator[psycopg.Cursor, None, None]:
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def fetchone(self, sql: str, params: dict[str, Any] | None = None) -> tuple | None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchone()

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})

    def execute_returning(self, sql: str, params: dict[str, Any] | None = None) -> tuple | None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchone()


class StagingPostgresRepository:
    def __init__(self, db: PostgresDB) -> None:
        self.db = db

    def get_by_id_stone(self, id_stone: str) -> tuple | None:
        return self.db.fetchone(pg.SELECT_REGISTRO_POR_ID_STONE, {"id_stone": id_stone})

    def get_maquininha_config(self, nr_serie: str) -> dict:
        row = self.db.fetchone(pg.SELECT_MAQUININHA_CONFIG, {"nr_serie_maquininha": nr_serie})
        if not row:
            raise ValueError(f"Maquininha {nr_serie} não cadastrada em maquininha_stone")
        return {
            "nr_serie_maquininha": row[0],
            "cd_caixa": row[1],
            "cd_transacao_financeira": row[2],
        }

    def find_maquininha_config(self, nr_serie: str) -> dict | None:
        """Retorna config ou None (sem raise) — usado no fluxo Sem Tesouraria."""
        row = self.db.fetchone(pg.SELECT_MAQUININHA_CONFIG, {"nr_serie_maquininha": nr_serie})
        if not row:
            return None
        return {
            "nr_serie_maquininha": row[0],
            "cd_caixa": row[1],
            "cd_transacao_financeira": row[2],
        }

    def get_bandeira_tasy(self, tipo_api: str, bandeira: str) -> int | None:
        """Resolve id Tasy via mapeamento Cotolengo (tipo/bandeira numéricos)."""
        cd_tipo = map_tipo_para_local(tipo_api)
        if cd_tipo is None:
            return None

        cd_bandeira = map_bandeira_para_local(bandeira)
        row = None
        if cd_bandeira is not None:
            row = self.db.fetchone(
                pg.SELECT_CARTAO_BANDEIRA,
                {"cd_tipo_transacao": cd_tipo, "cd_bandeira": cd_bandeira},
            )
        if not row:
            # PIX e fallbacks sem bandeira (cd_bandeira IS NULL)
            row = self.db.fetchone(
                pg.SELECT_TRANSACAO_SEM_BANDEIRA,
                {"cd_tipo_transacao": cd_tipo},
            )
        # Fallbacks: débito sem bandeira → Pix (3); pix explícito já usa tipo 3
        if not row and tipo_api in ("debit_card", "pix"):
            row = self.db.fetchone(
                pg.SELECT_TRANSACAO_SEM_BANDEIRA,
                {"cd_tipo_transacao": 3},
            )
        if not row:
            return None
        valor = int(row[0])
        # 0 = placeholder inválido
        return valor if valor > 0 else None


    def update_status(self, nr_sequencia: int | None, status: int, obs: str) -> None:
        if nr_sequencia is None:
            return
        self.db.execute(
            pg.UPDATE_STATUS_TRANSACAO,
            {"cd_status": status, "ds_obs_processo": obs[:500], "nr_sequencia": nr_sequencia},
        )

    def ensure_registro(
        self,
        tx: TransacaoCartao,
        status: int,
        obs: str,
        cd_caixa: int | None = None,
    ) -> int | None:
        existente = self.get_by_id_stone(tx.id_stone)
        if existente:
            if existente[1] != 5:
                self.update_status(existente[0], status, obs)
            return existente[0]

        if cd_caixa is None:
            try:
                cd_caixa = self.get_maquininha_config(tx.nr_serie_maquininha)["cd_caixa"]
            except Exception:
                cd_caixa = 0

        dt = tx.dt_movimentacao.date() if hasattr(tx.dt_movimentacao, "date") else tx.dt_movimentacao
        params = {
            "nr_serie_maquininha": tx.nr_serie_maquininha,
            "cd_caixa": cd_caixa,
            "dt_movimentacao": dt,
            "cd_autorizacao": tx.cd_autorizacao,
            "vl_transacao": to_float_money(tx.vl_transacao),
            "id_stone": tx.id_stone,
            # Mantém o tipo original da Stone (prepaid_debit ≠ debit_card no staging/portal)
            "cd_tipo_transacao": tx.cd_tipo_transacao.value,
            "cd_bandeira": (map_stone_brand(tx.cd_bandeira) if tx.cd_bandeira else None),
            "qt_parcelas": tx.qt_parcelas,
            "ie_transacao_parcelada": "S" if (tx.ie_transacao_parcelada or tx.qt_parcelas > 1) else "N",
            "cd_status": status,
            "ds_obs_processo": obs[:500],
        }
        try:
            row = self.db.execute_returning(pg.INSERT_REGISTRO_MAQUININHA, params)
            return row[0] if row else None
        except Exception as exc:
            logger.warning("Insert staging falhou (%s); update por id_stone", exc)
            self.db.execute(
                pg.UPDATE_STATUS_POR_ID_STONE,
                {"cd_status": status, "ds_obs_processo": obs[:500], "id_stone": tx.id_stone},
            )
            row = self.get_by_id_stone(tx.id_stone)
            return row[0] if row else None

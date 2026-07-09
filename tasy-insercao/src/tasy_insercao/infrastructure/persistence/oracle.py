from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import oracledb

from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.queries import oracle_queries as ora

logger = get_logger(__name__)


class OracleDB:
    def __init__(self) -> None:
        self._conn: oracledb.Connection | None = None

    def connect(self) -> oracledb.Connection:
        if self._conn is None:
            if not settings.ORACLE_USER or not settings.ORACLE_DSN:
                raise RuntimeError("ORACLE_USER/ORACLE_DSN não configurados")
            logger.info("Conectando Oracle")
            self._conn = oracledb.connect(
                user=settings.ORACLE_USER,
                password=settings.ORACLE_PASS,
                dsn=settings.ORACLE_DSN,
            )
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def reset(self) -> None:
        """Força reconexão após falha de rede."""
        self.close()

    @contextmanager
    def cursor(self) -> Generator[oracledb.Cursor, None, None]:
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

    def execute_returning(self, sql: str, params: dict[str, Any] | None = None) -> int:
        with self.cursor() as cur:
            bind = dict(params or {})
            out_var = cur.var(int)
            bind["id_retornado"] = out_var
            cur.execute(sql, bind)
            value = out_var.getvalue()
            if isinstance(value, list):
                return int(value[0])
            return int(value)


class TasyOracleRepository:
    def __init__(self, db: OracleDB) -> None:
        self.db = db

    def exists_movto_by_id_stone(self, id_stone: str) -> bool:
        row = self.db.fetchone(
            ora.SELECT_MOVTO_POR_ID_STONE,
            {"ds_observacao": f"%ID stone - {id_stone}%"},
        )
        return row is not None

    def ensure_caixa_saldo_diario(self, nr_seq_caixa: int, dt_saldo: str) -> int:
        existente = self.db.fetchone(
            ora.SELECT_EXISTENCIA_CAIXA_SALDO_DIARIO,
            {"nr_seq_caixa": nr_seq_caixa, "dt_saldo": dt_saldo},
        )
        if existente:
            return int(existente[0])
        return self.db.execute_returning(
            ora.INSERT_CAIXA_SALDO_DIARIO,
            {"nr_seq_caixa": nr_seq_caixa, "dt_saldo": dt_saldo},
        )

    def inserir_caixa_receb(self, nr_seq_saldo: int, dt: str, cd_trans_fin: int) -> int:
        return self.db.execute_returning(
            ora.INSERT_CAIXA_RECEB,
            {
                "nr_seq_saldo_caixa": nr_seq_saldo,
                "dt_recebimento": dt,
                "nr_seq_trans_financ": cd_trans_fin,
            },
        )

    def inserir_movto_cartao(self, params: dict) -> None:
        self.db.execute(ora.INSERT_MOVTO_CARTAO, params)

    def inserir_movto_cartao_parcelado(self, params: dict) -> None:
        self.db.execute(ora.INSERT_MOVTO_CARTAO_PARCELADO, params)

    def inserir_documento(self, params: dict) -> None:
        self.db.execute(ora.INSERT_MOVTO_TRANS_FINANC, params)

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterator

import oracledb

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OracleDB:
    """Wrapper fino sobre oracledb (thin mode por default)."""

    def __init__(
        self,
        user: str | None = None,
        password: str | None = None,
        dsn: str | None = None,
    ) -> None:
        self.user = user or settings.ORACLE_USER
        self.password = password or settings.ORACLE_PASS
        self.dsn = dsn or settings.ORACLE_DSN
        self._conn: oracledb.Connection | None = None

    def connect(self) -> oracledb.Connection:
        if self._conn is None:
            if not self.user or not self.dsn:
                raise RuntimeError("Credenciais Oracle não configuradas (ORACLE_USER/ORACLE_DSN)")
            logger.info("Conectando Oracle | dsn=%s", self.dsn[:40] + "...")
            self._conn = oracledb.connect(user=self.user, password=self.password, dsn=self.dsn)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("Oracle desconectado")

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

    def fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return list(cur.fetchall())

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})

    def execute_returning(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        out_key: str = "id_retornado",
    ) -> int:
        """Executa INSERT/PLSQL com bind OUT `:id_retornado` e retorna o valor."""
        with self.cursor() as cur:
            bind: dict[str, Any] = dict(params or {})
            out_var = cur.var(int)
            bind[out_key] = out_var
            cur.execute(sql, bind)
            value = out_var.getvalue()
            if isinstance(value, list):
                return int(value[0])
            return int(value)

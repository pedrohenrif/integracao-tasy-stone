from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Iterator

import psycopg
from psycopg.rows import tuple_row

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PostgresDB:
    """Wrapper fino sobre psycopg3."""

    def __init__(self, conninfo: str | None = None) -> None:
        self.conninfo = conninfo or settings.ASYNC_POSTGRES_URL
        self._conn: psycopg.Connection | None = None

    def connect(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            if not settings.POSTGRES_DB:
                raise RuntimeError("Credenciais Postgres não configuradas (POSTGRES_DB)")
            logger.info(
                "Conectando Postgres | host=%s db=%s",
                settings.POSTGRES_HOST,
                settings.POSTGRES_DB,
            )
            self._conn = psycopg.connect(self.conninfo, row_factory=tuple_row)
        return self._conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
            self._conn = None
            logger.info("Postgres desconectado")

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

    def fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return list(cur.fetchall())

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})

    def execute_returning(self, sql: str, params: dict[str, Any] | None = None) -> tuple | None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchone()

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

    def execute_returning_number(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        *,
        out_name: str = "vl_troco",
    ) -> float:
        with self.cursor() as cur:
            bind = dict(params or {})
            out_var = cur.var(oracledb.DB_TYPE_NUMBER)
            bind[out_name] = out_var
            cur.execute(sql, bind)
            value = out_var.getvalue()
            if isinstance(value, list):
                return float(value[0] or 0)
            return float(value or 0)


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

    def inserir_movto_cartao(self, params: dict) -> int:
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO, params)

    def inserir_movto_cartao_sem_tesouraria(self, params: dict) -> int:
        """Insert movto sem nr_seq_caixa_rec (maquininha/caixa não cadastrados)."""
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO_SEM_TESOURARIA, params)

    def inserir_movto_cartao_parcelado(self, params: dict) -> int:
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO_PARCELADO, params)

    def inserir_documento(self, params: dict) -> None:
        self.db.execute(ora.INSERT_MOVTO_TRANS_FINANC, params)

    def fechar_caixa_receb(self, nr_seq_caixa_rec: int, dt_fechamento: str) -> float:
        """
        Confirma o recebimento no Tasy (botão Tesouraria / Ctrl+F6).
        Não usar no fluxo Sem Tesouraria (sem caixa_receb).
        Retorna vl_troco calculado pela procedure.
        """
        logger.info(
            "Fechar_caixa_receb | início | nr_seq_caixa_rec=%s | dt=%s",
            nr_seq_caixa_rec,
            dt_fechamento,
        )
        vl_troco = self.db.execute_returning_number(
            ora.CALL_FECHAR_CAIXA_RECEB,
            {
                "nr_seq_caixa_rec": nr_seq_caixa_rec,
                "dt_fechamento": dt_fechamento,
            },
            out_name="vl_troco",
        )
        logger.info(
            "Fechar_caixa_receb | ok | nr_seq_caixa_rec=%s | vl_troco=%s",
            nr_seq_caixa_rec,
            vl_troco,
        )
        return vl_troco

    def corrigir_vinculo_documentos_stone(self) -> int:
        """Preenche NR_SEQ_MOVTO_CARTAO / saldo / caixa nos docs Stone órfãos."""
        with self.db.cursor() as cur:
            cur.execute(ora.UPDATE_DOC_STONE_VINCULO_CARTAO)
            return int(cur.rowcount or 0)

    def corrigir_trans_e_valor_documentos_stone(self) -> int:
        """Alinha nr_seq_trans_financ ao caixa_receb e vl ao total do cartão."""
        with self.db.cursor() as cur:
            cur.execute(ora.UPDATE_DOC_STONE_TRANS_E_VALOR)
            return int(cur.rowcount or 0)

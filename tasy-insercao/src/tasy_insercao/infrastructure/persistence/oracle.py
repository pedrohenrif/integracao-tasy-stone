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

    def fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return list(cur.fetchall())

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params or {})

    def execute_dml(self, sql: str, params: dict[str, Any] | None = None) -> int:
        with self.cursor() as cur:
            cur.execute(sql, params or {})
            return int(cur.rowcount or 0)

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

    def get_caixa_receb_para_confirmar(self, id_stone: str) -> dict[str, Any] | None:
        """Retorna nr_seq_caixa_rec + dt para retry do FECHAR, ou None."""
        row = self.db.fetchone(
            ora.SELECT_CAIXA_RECEB_PARA_CONFIRMAR,
            {"ds_observacao": f"%ID stone - {id_stone}%"},
        )
        if not row:
            return None
        return {
            "nr_seq_caixa_rec": int(row[0]),
            "dt_recebimento": str(row[1]),
            "ja_fechado": str(row[2] or "N").upper() == "S",
        }

    def ensure_documento_por_id_stone(self, id_stone: str) -> bool:
        """Garante documento agregado (soma) do recebimento ligado ao id_stone."""
        info = self.get_caixa_receb_para_confirmar(id_stone)
        if not info:
            return False
        nr_seq_caixa_rec = int(info["nr_seq_caixa_rec"])
        cr = self.db.fetchone(
            ora.SELECT_CAIXA_RECEB_TRANS_E_DATA,
            {"nr_seq_caixa_rec": nr_seq_caixa_rec},
        )
        if not cr or cr[0] is None:
            return False
        self.upsert_documento_agregado(
            nr_seq_caixa_rec=nr_seq_caixa_rec,
            nr_seq_trans_financ=int(cr[0]),
            dt_transacao=cr[1],
        )
        logger.info(
            "Documento agregado | id_stone=%s | caixa_receb=%s",
            id_stone,
            nr_seq_caixa_rec,
        )
        return True

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

    def ensure_caixa_receb_aberto(
        self,
        nr_seq_saldo: int,
        dt: str,
        cd_trans_fin: int,
        nr_serie_maquininha: str | None = None,
    ) -> int:
        """
        Reusa recebimento Stone aberto do saldo+serial; cria se não houver.

        Com serial: 1 caixa_receb por maquininha no mesmo caixa/dia.
        Sem serial: fallback legado (1 aberto por saldo).
        """
        serial = (nr_serie_maquininha or "").strip()
        if serial:
            row = self.db.fetchone(
                ora.SELECT_CAIXA_RECEB_ABERTO_STONE_POR_SERIAL,
                {
                    "nr_seq_saldo_caixa": nr_seq_saldo,
                    "nr_serie_maquininha": serial,
                },
            )
        else:
            row = self.db.fetchone(
                ora.SELECT_CAIXA_RECEB_ABERTO_STONE,
                {"nr_seq_saldo_caixa": nr_seq_saldo},
            )
        if row:
            return int(row[0])
        return self.inserir_caixa_receb(nr_seq_saldo, dt, cd_trans_fin)

    def listar_caixa_receb_abertos_stone(
        self,
        dt_recebimento: str,
        *,
        nr_seq_caixa: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recebimentos Stone com dt_fechamento IS NULL no dia informado.
        Usado na confirmação diferida (1 FECHAR por caixa_receb unificado).
        """
        rows = self.db.fetchall(
            ora.SELECT_CAIXA_RECEB_ABERTOS_STONE_POR_DATA,
            {
                "dt_recebimento": dt_recebimento,
                "nr_seq_caixa": nr_seq_caixa,
            },
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "nr_seq_caixa_rec": int(row[0]),
                    "dt_recebimento": str(row[1]),
                    "nr_seq_caixa": int(row[2]) if row[2] is not None else None,
                    "nr_seq_trans_financ": int(row[3]) if row[3] is not None else None,
                }
            )
        return out

    def inserir_caixa_receb(self, nr_seq_saldo: int, dt: str, cd_trans_fin: int) -> int:
        return self.db.execute_returning(
            ora.INSERT_CAIXA_RECEB,
            {
                "nr_seq_saldo_caixa": nr_seq_saldo,
                "dt_recebimento": dt,
                "nr_seq_trans_financ": cd_trans_fin,
            },
        )

    def upsert_documento_agregado(
        self,
        *,
        nr_seq_caixa_rec: int,
        nr_seq_trans_financ: int,
        dt_transacao: Any,
    ) -> float:
        """1 documento por recebimento = soma dos movto_cartao_cr."""
        soma_row = self.db.fetchone(
            ora.SELECT_SOMA_MOVTO_POR_CAIXA_RECEB,
            {"nr_seq_caixa_rec": nr_seq_caixa_rec},
        )
        vl = float((soma_row or [0])[0] or 0)
        doc = self.db.fetchone(
            ora.SELECT_DOC_AGREGADO_POR_CAIXA_RECEB,
            {"nr_seq_caixa_rec": nr_seq_caixa_rec},
        )
        if doc:
            self.db.execute(
                ora.UPDATE_DOC_AGREGADO_VALOR,
                {
                    "vl_transacao": vl,
                    "nr_seq_trans_financ": nr_seq_trans_financ,
                    "nr_seq_doc": int(doc[0]),
                },
            )
            logger.info(
                "Documento agregado atualizado | caixa_receb=%s | doc=%s | vl=%s",
                nr_seq_caixa_rec,
                doc[0],
                vl,
            )
        else:
            self.db.execute(
                ora.INSERT_MOVTO_TRANS_FINANC_AGREGADO,
                {
                    "nr_seq_caixa_rec": nr_seq_caixa_rec,
                    "dt_transacao": dt_transacao,
                    "nr_seq_trans_financ": nr_seq_trans_financ,
                    "vl_transacao": vl,
                },
            )
            logger.info(
                "Documento agregado criado | caixa_receb=%s | vl=%s",
                nr_seq_caixa_rec,
                vl,
            )
        return vl

    def count_movtos_caixa_receb(self, nr_seq_caixa_rec: int) -> int:
        row = self.db.fetchone(
            ora.SELECT_QTD_MOVTO_POR_CAIXA_RECEB,
            {"nr_seq_caixa_rec": nr_seq_caixa_rec},
        )
        return int((row or [0])[0] or 0)

    def inserir_movto_cartao(self, params: dict) -> int:
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO, params)

    def inserir_movto_cartao_sem_tesouraria(self, params: dict) -> int:
        """Insert movto sem nr_seq_caixa_rec (maquininha/caixa não cadastrados)."""
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO_SEM_TESOURARIA, params)

    def inserir_movto_cartao_parcelado(self, params: dict) -> int:
        return self.db.execute_returning(ora.INSERT_MOVTO_CARTAO_PARCELADO, params)

    def inserir_documento(self, params: dict) -> None:
        self.db.execute(ora.INSERT_MOVTO_TRANS_FINANC, params)

    def liberar_doc_lote_antes_fechar(self, nr_seq_caixa_rec: int) -> int:
        """
        Zera nr_seq_caixa/nr_seq_lote em docs Stone do recebimento ainda sem
        dt_fechamento_lote. Evita ORA-20011 'lote aberto' (docs legados).
        """
        return self.db.execute_dml(
            ora.LIBERAR_DOC_LOTE_ANTES_FECHAR,
            {"nr_seq_caixa_rec": nr_seq_caixa_rec},
        )

    def fechar_caixa_receb(self, nr_seq_caixa_rec: int, dt_fechamento: str) -> float:
        """
        Confirma o recebimento no Tasy (botão Tesouraria / Ctrl+F6).
        Chamar somente após inserir movto_trans_financ (documento).
        Não usar no fluxo Sem Tesouraria (sem caixa_receb).
        Retorna vl_troco calculado pela procedure.
        """
        liberados = self.liberar_doc_lote_antes_fechar(nr_seq_caixa_rec)
        if liberados:
            logger.info(
                "Fechar_caixa_receb | docs liberados (nr_seq_caixa null) | "
                "nr_seq_caixa_rec=%s | qtd=%s",
                nr_seq_caixa_rec,
                liberados,
            )
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
                "nm_usuario": settings.TASY_NM_USUARIO,
                "cd_estabelecimento": settings.TASY_CD_ESTABELECIMENTO,
                "cd_perfil": settings.TASY_CD_PERFIL,
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

    def preview_purge_stone(self, id_stone: str, nm_usuario: str) -> dict[str, Any] | None:
        """Resolve PKs Oracle do id_stone + nm_usuario. None se não achar movto Stone."""
        obs = f"%ID stone - {id_stone}%"
        row = self.db.fetchone(
            ora.SELECT_PURGE_TARGET,
            {"nm_usuario": nm_usuario, "ds_observacao": obs},
        )
        if not row:
            return None
        nr_movto = int(row[0])
        qtd_parcelas = 0
        try:
            prow = self.db.fetchone(
                ora.SELECT_PURGE_QTD_PARCELAS, {"nr_seq_movto": nr_movto}
            )
            qtd_parcelas = int((prow or [0])[0] or 0)
        except oracledb.DatabaseError as exc:
            logger.warning("Purge preview parcelas | movto=%s | %s", nr_movto, exc)
        return {
            "nr_seq_movto": nr_movto,
            "nr_seq_caixa_rec": int(row[1]) if row[1] is not None else None,
            "vl_transacao": float(row[2] or 0),
            "dt_transacao": str(row[3]) if row[3] is not None else None,
            "ja_fechado": str(row[4] or "N").upper() == "S",
            "qtd_docs": int(row[5] or 0),
            "qtd_parcelas": qtd_parcelas,
        }
    def purge_stone_transaction(
        self,
        id_stone: str,
        nm_usuario: str,
        *,
        allow_fechado: bool,
    ) -> dict[str, Any]:
        """
        Ordem: parcelas → movto_cartao → documento → caixa_receb (nunca caixa/saldo).
        Documento é desvinculado do movto antes de apagar o cartão (FK).
        Exige nm_usuario + ID stone na observação.
        """
        obs = f"%ID stone - {id_stone}%"
        target = self.preview_purge_stone(id_stone, nm_usuario)
        if not target:
            return {
                "ok": False,
                "blocked_reason": "Movto Stone não encontrado no Oracle",
                "deleted": {},
            }
        if target["ja_fechado"] and not allow_fechado:
            return {
                "ok": False,
                "blocked_reason": "Recebimento confirmado (dt_fechamento). Marque permitir confirmados.",
                "target": target,
                "deleted": {},
            }

        nr_movto = target["nr_seq_movto"]
        nr_receb = target["nr_seq_caixa_rec"]
        deleted: dict[str, int] = {}

        with self.db.cursor() as cur:
            # 1) Parcelas do movto (filho do cartão)
            try:
                cur.execute(ora.DELETE_PURGE_PARCELAS, {"nr_seq_movto": nr_movto})
                deleted["parcelas"] = int(cur.rowcount or 0)
            except oracledb.DatabaseError as exc:
                logger.warning(
                    "Purge parcelas | id_stone=%s | movto=%s | %s",
                    id_stone,
                    nr_movto,
                    exc,
                )
                deleted["parcelas"] = 0

            # 2) Desvincula documento do movto (evita FK ao apagar cartão antes do doc)
            cur.execute(
                ora.UNLINK_PURGE_DOCS_MOVTO,
                {
                    "nm_usuario": nm_usuario,
                    "nr_seq_movto": nr_movto,
                    "nr_seq_caixa_rec": nr_receb,
                },
            )

            # 3) Movto cartão
            cur.execute(
                ora.DELETE_PURGE_MOVTO,
                {
                    "nr_seq_movto": nr_movto,
                    "nm_usuario": nm_usuario,
                    "ds_observacao": obs,
                },
            )
            deleted["movto"] = int(cur.rowcount or 0)
            if deleted["movto"] != 1:
                raise RuntimeError(
                    f"Purge abortado: movto não removido (rowcount={deleted['movto']}) "
                    f"id_stone={id_stone}"
                )

            # 4) Documento (movto_trans_financ)
            cur.execute(
                ora.DELETE_PURGE_DOCS,
                {
                    "nm_usuario": nm_usuario,
                    "nr_seq_movto": nr_movto,
                    "nr_seq_caixa_rec": nr_receb,
                },
            )
            deleted["docs"] = int(cur.rowcount or 0)

            # 5) Recebimento (só se não restar movto/doc ligado)
            if nr_receb is not None:
                cur.execute(
                    ora.DELETE_PURGE_CAIXA_RECEB,
                    {
                        "nr_seq_caixa_rec": nr_receb,
                        "nm_usuario": nm_usuario,
                    },
                )
                deleted["caixa_receb"] = int(cur.rowcount or 0)
            else:
                deleted["caixa_receb"] = 0

        logger.info(
            "Purge Oracle | id_stone=%s | usuario=%s | deleted=%s",
            id_stone,
            nm_usuario,
            deleted,
        )
        return {"ok": True, "target": target, "deleted": deleted}

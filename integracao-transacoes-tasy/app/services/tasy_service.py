from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from workalendar.america import Brazil

from app.core.logging import get_logger
from app.core.oracle import OracleDB
from app.core.postgres import PostgresDB
from app.queries import oracle_queries as ora
from app.queries import postgre_queries as pg
from app.schemas.cartao import TipoTransacaoCartao, TransacaoCartao
from app.utils.money import map_stone_brand, map_tipo_para_api, to_float_money

logger = get_logger(__name__)

STATUS_PENDENTE = 1
STATUS_INTEGRADO = 5
STATUS_ERRO = 6

# Documento financeiro no Tasy (hardcoded no GA111)
CD_TRANS_FINANC_DOCUMENTO = 149


@dataclass
class ResultadoIntegracao:
    id_stone: str
    status: int
    mensagem: str
    nr_sequencia_pg: int | None = None
    nr_seq_caixa_receb: int | None = None


class TasyService:
    """
    Consumer business logic: Caixa → Dia (caixa_receb) → Transação → Documento.
    Processa uma TransacaoCartao por chamada (mensagem da fila).
    """

    def __init__(self, postgres: PostgresDB, oracle: OracleDB) -> None:
        self.pg = postgres
        self.oracle = oracle
        self.cal = Brazil()

    def processar_transacao_cartao(self, tx: TransacaoCartao) -> ResultadoIntegracao:
        logger.info(
            "Consumido | cartao | id_stone=%s | terminal=%s | iniciando Tasy",
            tx.id_stone,
            tx.nr_serie_maquininha,
        )

        existente = self.pg.fetchone(
            pg.SELECT_REGISTRO_POR_ID_STONE,
            {"id_stone": tx.id_stone},
        )
        if existente and existente[1] == STATUS_INTEGRADO:
            msg = "Já integrado (idempotente)"
            logger.info("Idempotente | id_stone=%s | %s", tx.id_stone, msg)
            return ResultadoIntegracao(tx.id_stone, STATUS_INTEGRADO, msg, existente[0])

        if self._ja_existe_no_tasy(tx.id_stone):
            nr_seq = self._ensure_staging(tx, STATUS_INTEGRADO, "Já existia no Tasy (idempotente)")
            return ResultadoIntegracao(
                tx.id_stone,
                STATUS_INTEGRADO,
                "Já existia no Tasy (idempotente)",
                nr_seq,
            )

        try:
            config = self._buscar_config_maquininha(tx.nr_serie_maquininha)
            cd_caixa = config["cd_caixa"]
            cd_trans_fin = config["cd_transacao_financeira"]
            dt_saldo = self._data_saldo(tx.dt_movimentacao)

            nr_seq_pg = self._ensure_staging(tx, STATUS_PENDENTE, "Em processamento", cd_caixa=cd_caixa)

            nr_seq_saldo = self._processo_caixa_saldo_diario(cd_caixa, dt_saldo)
            nr_seq_receb = self._processo_caixa_receb(nr_seq_saldo, dt_saldo, cd_trans_fin)

            self._inserir_movto_cartao(tx, nr_seq_receb, dt_saldo)
            self._inserir_documento(nr_seq_receb, dt_saldo)

            self._update_status(nr_seq_pg, STATUS_INTEGRADO, "Transação Integrada")
            logger.info(
                "Inserido | cartao | id_stone=%s | caixa_receb=%s | status=5",
                tx.id_stone,
                nr_seq_receb,
            )
            return ResultadoIntegracao(
                tx.id_stone,
                STATUS_INTEGRADO,
                "Transação Integrada",
                nr_seq_pg,
                nr_seq_receb,
            )
        except Exception as exc:
            logger.exception("Erro ao integrar id_stone=%s: %s", tx.id_stone, exc)
            nr_seq = None
            try:
                nr_seq = self._ensure_staging(tx, STATUS_ERRO, str(exc)[:500])
            except Exception:
                pass
            return ResultadoIntegracao(tx.id_stone, STATUS_ERRO, str(exc), nr_seq)

    def _buscar_config_maquininha(self, nr_serie: str) -> dict[str, Any]:
        row = self.pg.fetchone(
            pg.SELECT_MAQUININHA_CONFIG,
            {"nr_serie_maquininha": nr_serie},
        )
        if not row:
            raise ValueError(f"Maquininha {nr_serie} não cadastrada em maquininha_stone")
        return {
            "nr_serie_maquininha": row[0],
            "cd_caixa": row[1],
            "cd_transacao_financeira": row[2],
        }

    def _data_saldo(self, dt_movimentacao: datetime | date) -> date:
        if isinstance(dt_movimentacao, datetime):
            return dt_movimentacao.date()
        return dt_movimentacao

    def _ja_existe_no_tasy(self, id_stone: str) -> bool:
        obs_like = f"%ID stone - {id_stone}%"
        row = self.oracle.fetchone(
            ora.SELECT_MOVTO_POR_ID_STONE,
            {"ds_observacao": obs_like},
        )
        return row is not None

    def _ensure_staging(
        self,
        tx: TransacaoCartao,
        status: int,
        obs: str,
        cd_caixa: int | None = None,
    ) -> int | None:
        existente = self.pg.fetchone(
            pg.SELECT_REGISTRO_POR_ID_STONE,
            {"id_stone": tx.id_stone},
        )
        tipo_api = map_tipo_para_api(tx.cd_tipo_transacao.value)
        bandeira = map_stone_brand(tx.cd_bandeira)
        ie_parc = "S" if tx.ie_transacao_parcelada or tx.qt_parcelas > 1 else "N"
        dt = self._data_saldo(tx.dt_movimentacao)

        if existente:
            nr_seq = existente[0]
            if existente[1] != STATUS_INTEGRADO:
                self._update_status(nr_seq, status, obs)
            return nr_seq

        if cd_caixa is None:
            try:
                cfg = self._buscar_config_maquininha(tx.nr_serie_maquininha)
                cd_caixa = cfg["cd_caixa"]
            except Exception:
                cd_caixa = 0

        params = {
            "nr_serie_maquininha": tx.nr_serie_maquininha,
            "cd_caixa": cd_caixa,
            "dt_movimentacao": dt,
            "cd_autorizacao": tx.cd_autorizacao,
            "vl_transacao": to_float_money(tx.vl_transacao),
            "id_stone": tx.id_stone,
            "cd_tipo_transacao": tipo_api,
            "cd_bandeira": bandeira if bandeira != "none" else None,
            "qt_parcelas": tx.qt_parcelas,
            "ie_transacao_parcelada": ie_parc,
            "cd_status": status,
            "ds_obs_processo": obs[:500],
        }
        try:
            row = self.pg.execute_returning(pg.INSERT_REGISTRO_MAQUININHA, params)
            return row[0] if row else None
        except Exception as exc:
            # Pode falhar se colunas diferirem no schema; tenta só update por id_stone
            logger.warning("Insert staging falhou (%s); tentando update por id_stone", exc)
            self.pg.execute(
                pg.UPDATE_STATUS_POR_ID_STONE,
                {
                    "cd_status": status,
                    "ds_obs_processo": obs[:500],
                    "id_stone": tx.id_stone,
                },
            )
            row = self.pg.fetchone(pg.SELECT_REGISTRO_POR_ID_STONE, {"id_stone": tx.id_stone})
            return row[0] if row else None

    def _update_status(self, nr_sequencia: int | None, status: int, obs: str) -> None:
        if nr_sequencia is None:
            return
        self.pg.execute(
            pg.UPDATE_STATUS_TRANSACAO,
            {
                "cd_status": status,
                "ds_obs_processo": obs[:500],
                "nr_sequencia": nr_sequencia,
            },
        )

    def _processo_caixa_saldo_diario(self, nr_seq_caixa: int, dt_saldo: date) -> int:
        dt_str = dt_saldo.strftime("%Y-%m-%d")
        logger.info("Caixa | verificando saldo diário caixa=%s data=%s", nr_seq_caixa, dt_str)
        existente = self.oracle.fetchone(
            ora.SELECT_EXISTENCIA_CAIXA_SALDO_DIARIO,
            {"nr_seq_caixa": nr_seq_caixa, "dt_saldo": dt_str},
        )
        if existente:
            logger.info("Caixa | já aberto nr_sequencia=%s", existente[0])
            return int(existente[0])

        nr = self.oracle.execute_returning(
            ora.INSERT_CAIXA_SALDO_DIARIO,
            {"nr_seq_caixa": nr_seq_caixa, "dt_saldo": dt_str},
        )
        logger.info("Caixa | aberto nr_sequencia=%s", nr)
        return nr

    def _processo_caixa_receb(
        self,
        nr_seq_saldo_caixa: int,
        dt_recebimento: date,
        cd_transacao_financeira: int,
    ) -> int:
        dt_str = dt_recebimento.strftime("%Y-%m-%d")
        logger.info("Dia | inserindo caixa_receb saldo=%s", nr_seq_saldo_caixa)
        nr = self.oracle.execute_returning(
            ora.INSERT_CAIXA_RECEB,
            {
                "nr_seq_saldo_caixa": nr_seq_saldo_caixa,
                "dt_recebimento": dt_str,
                "nr_seq_trans_financ": cd_transacao_financeira,
            },
        )
        logger.info("Dia | caixa_receb=%s", nr)
        return nr

    def _resolver_bandeira_tasy(self, tx: TransacaoCartao) -> int:
        tipo_api = map_tipo_para_api(tx.cd_tipo_transacao.value)
        bandeira = map_stone_brand(tx.cd_bandeira)

        row = self.pg.fetchone(
            pg.SELECT_CARTAO_BANDEIRA,
            {"ds_tipo_transacao_api": tipo_api, "ds_bandeira_api": bandeira},
        )
        if not row and bandeira != "none":
            # tenta BrandId cru (caso o mapeamento use o código numérico)
            row = self.pg.fetchone(
                pg.SELECT_CARTAO_BANDEIRA,
                {
                    "ds_tipo_transacao_api": tipo_api,
                    "ds_bandeira_api": str(tx.cd_bandeira).strip() if tx.cd_bandeira else "none",
                },
            )
        if not row:
            row = self.pg.fetchone(
                pg.SELECT_TRANSACAO_SEM_BANDEIRA,
                {"ds_tipo_transacao_api": tipo_api},
            )
        if not row:
            raise ValueError(
                f"Mapeamento Tasy não encontrado para {tipo_api}/{bandeira}"
            )
        return int(row[0])

    def _calcular_vencimento(self, tipo_api: str, dt_recebimento: date) -> date:
        if tipo_api == "credit_card":
            dt_base = dt_recebimento + timedelta(days=30)
            while not self.cal.is_working_day(dt_base):
                dt_base += timedelta(days=1)
            return dt_base
        if tipo_api == "debit_card":
            return self.cal.add_working_days(dt_recebimento, 1)
        return dt_recebimento

    def _inserir_movto_cartao(
        self,
        tx: TransacaoCartao,
        nr_seq_caixa_rec: int,
        dt_recebimento: date,
    ) -> None:
        tipo_api = map_tipo_para_api(tx.cd_tipo_transacao.value)
        nr_seq_bandeira = self._resolver_bandeira_tasy(tx)
        vl = to_float_money(tx.vl_transacao)
        dt_venc = self._calcular_vencimento(tipo_api, dt_recebimento)
        ds_obs = f"Maquininha - {tx.nr_serie_maquininha} | ID stone - {tx.id_stone}"

        if tipo_api == "credit_card":
            ie_tipo = "C"
            nr_seq_trans_caixa = 72
            nr_seq_forma_pagto = 2
        else:
            ie_tipo = "D"
            nr_seq_trans_caixa = 73
            nr_seq_forma_pagto = 1

        parcelada = tx.ie_transacao_parcelada or tx.qt_parcelas > 1
        logger.info(
            "Transação | id_stone=%s | tipo=%s | parcelada=%s | bandeira_tasy=%s",
            tx.id_stone,
            tipo_api,
            parcelada,
            nr_seq_bandeira,
        )

        # dt_transacao / dt_primeira_parcela: binds sem TO_DATE → date Python
        if parcelada and tipo_api == "credit_card":
            self.oracle.execute(
                ora.INSERT_MOVTO_CARTAO_PARCELADO,
                {
                    "nr_seq_caixa_rec": nr_seq_caixa_rec,
                    "dt_transacao": dt_recebimento,
                    "vl_transacao": vl,
                    "nr_seq_trans_caixa": nr_seq_trans_caixa,
                    "ds_observacao": ds_obs,
                    "nr_seq_bandeira": nr_seq_bandeira,
                    "qt_parcelas": tx.qt_parcelas,
                    "nr_autorizacao": tx.cd_autorizacao or "",
                    "dt_primeira_parcela": dt_venc,
                },
            )
        else:
            self.oracle.execute(
                ora.INSERT_MOVTO_CARTAO,
                {
                    "ie_tipo_cartao": ie_tipo,
                    "nr_seq_caixa_rec": nr_seq_caixa_rec,
                    "dt_transacao": dt_recebimento,
                    "vl_transacao": vl,
                    "ds_observacao": ds_obs,
                    "nr_seq_bandeira": nr_seq_bandeira,
                    "nr_autorizacao": tx.cd_autorizacao or "",
                    "nr_seq_forma_pagto": nr_seq_forma_pagto,
                    "nr_seq_trans_caixa": nr_seq_trans_caixa,
                    "dt_primeira_parcela": dt_venc,
                },
            )

    def _inserir_documento(self, nr_seq_caixa_receb: int, dt_movimentacao: date) -> None:
        logger.info("Documento | movto_trans_financ caixa_receb=%s", nr_seq_caixa_receb)
        self.oracle.execute(
            ora.INSERT_MOVTO_TRANS_FINANC,
            {
                "nr_seq_caixa_rec": nr_seq_caixa_receb,
                "dt_transacao": dt_movimentacao,
                "nr_seq_trans_financ": CD_TRANS_FINANC_DOCUMENTO,
            },
        )

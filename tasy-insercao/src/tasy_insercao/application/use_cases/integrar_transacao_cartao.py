from __future__ import annotations

from datetime import date, datetime, timedelta

from workalendar.america import Brazil

from tasy_insercao.domain.integracao.models import (
    ResultadoIntegracao,
    StatusIntegracao,
    TransacaoCartao,
)
from tasy_insercao.domain.integracao.policies import (
    is_retryable_error,
    map_stone_brand,
    map_tipo_para_api,
    to_float_money,
)
from tasy_insercao.domain.integracao.ports import StagingRepositoryPort, TasyRepositoryPort
from tasy_insercao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

CD_TRANS_FINANC_DOCUMENTO = 149


class IntegrarTransacaoCartao:
    """
    Use case de domínio: Caixa → Dia → Transação → Documento.
    Idempotente por id_stone (PG status=5 ou movto no Oracle).
    """

    def __init__(self, staging: StagingRepositoryPort, tasy: TasyRepositoryPort) -> None:
        self.staging = staging
        self.tasy = tasy
        self.cal = Brazil()

    def execute(self, tx: TransacaoCartao) -> ResultadoIntegracao:
        logger.info(
            "Consumido | cartao | id_stone=%s | terminal=%s",
            tx.id_stone,
            tx.nr_serie_maquininha,
        )

        existente = self.staging.get_by_id_stone(tx.id_stone)
        if existente and existente[1] == StatusIntegracao.INTEGRADO.value:
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Já integrado (idempotente)",
                retryable=False,
                nr_sequencia_pg=existente[0],
            )

        if self.tasy.exists_movto_by_id_stone(tx.id_stone):
            nr = self.staging.ensure_registro(
                tx, StatusIntegracao.INTEGRADO.value, "Já existia no Tasy (idempotente)"
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Já existia no Tasy (idempotente)",
                retryable=False,
                nr_sequencia_pg=nr,
            )

        try:
            config = self.staging.get_maquininha_config(tx.nr_serie_maquininha)
            cd_caixa = config["cd_caixa"]
            cd_trans_fin = config["cd_transacao_financeira"]
            dt_saldo = self._data_saldo(tx.dt_movimentacao)
            dt_str = dt_saldo.strftime("%Y-%m-%d")

            nr_seq_pg = self.staging.ensure_registro(
                tx,
                StatusIntegracao.PROCESSANDO.value,
                "Em processamento",
                cd_caixa=cd_caixa,
            )

            nr_seq_saldo = self.tasy.ensure_caixa_saldo_diario(cd_caixa, dt_str)
            nr_seq_receb = self.tasy.inserir_caixa_receb(nr_seq_saldo, dt_str, cd_trans_fin)
            self._inserir_movto(tx, nr_seq_receb, dt_saldo)
            self.tasy.inserir_documento(
                {
                    "nr_seq_caixa_rec": nr_seq_receb,
                    "dt_transacao": dt_saldo,
                    "nr_seq_trans_financ": CD_TRANS_FINANC_DOCUMENTO,
                }
            )

            self.staging.update_status(
                nr_seq_pg, StatusIntegracao.INTEGRADO.value, "Transação Integrada"
            )
            logger.info("Inserido | id_stone=%s | caixa_receb=%s", tx.id_stone, nr_seq_receb)
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Transação Integrada",
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
                nr_seq_caixa_receb=nr_seq_receb,
            )
        except Exception as exc:
            retryable = is_retryable_error(exc)
            status = (
                StatusIntegracao.ERRO_RETRY if retryable else StatusIntegracao.ERRO_DEFINITIVO
            )
            logger.exception(
                "Falha | id_stone=%s | retryable=%s | %s",
                tx.id_stone,
                retryable,
                exc,
            )
            nr = None
            try:
                nr = self.staging.ensure_registro(tx, status.value, str(exc)[:500])
            except Exception:
                pass
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=status,
                mensagem=str(exc),
                retryable=retryable,
                nr_sequencia_pg=nr,
            )

    def _data_saldo(self, dt_movimentacao: datetime | date) -> date:
        if isinstance(dt_movimentacao, datetime):
            return dt_movimentacao.date()
        return dt_movimentacao

    def _calcular_vencimento(self, tipo_api: str, dt_recebimento: date) -> date:
        if tipo_api == "credit_card":
            dt_base = dt_recebimento + timedelta(days=30)
            while not self.cal.is_working_day(dt_base):
                dt_base += timedelta(days=1)
            return dt_base
        if tipo_api == "debit_card":
            return self.cal.add_working_days(dt_recebimento, 1)
        return dt_recebimento

    def _inserir_movto(self, tx: TransacaoCartao, nr_seq_caixa_rec: int, dt_recebimento: date) -> None:
        tipo_api = map_tipo_para_api(tx.cd_tipo_transacao.value)
        bandeira = map_stone_brand(tx.cd_bandeira)
        nr_seq_bandeira = self.staging.get_bandeira_tasy(tipo_api, bandeira)
        if nr_seq_bandeira is None and tx.cd_bandeira:
            nr_seq_bandeira = self.staging.get_bandeira_tasy(tipo_api, str(tx.cd_bandeira).strip())
        if nr_seq_bandeira is None:
            raise ValueError(f"Mapeamento Tasy não encontrado para {tipo_api}/{bandeira}")

        vl = to_float_money(tx.vl_transacao)
        dt_venc = self._calcular_vencimento(tipo_api, dt_recebimento)
        ds_obs = f"Maquininha - {tx.nr_serie_maquininha} | ID stone - {tx.id_stone}"
        parcelada = tx.ie_transacao_parcelada or tx.qt_parcelas > 1

        if tipo_api == "credit_card":
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "C", 72, 2
        else:
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "D", 73, 1

        if parcelada and tipo_api == "credit_card":
            self.tasy.inserir_movto_cartao_parcelado(
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
                }
            )
        else:
            self.tasy.inserir_movto_cartao(
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
                }
            )

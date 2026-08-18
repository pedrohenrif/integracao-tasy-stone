from __future__ import annotations

from datetime import date, datetime, timedelta

from workalendar.america import Brazil

from tasy_insercao.domain.integracao.models import (
    ResultadoIntegracao,
    StatusIntegracao,
    TransacaoCartao,
)
from tasy_insercao.domain.integracao.policies import (
    is_debito_tasy,
    is_retryable_error,
    map_stone_brand,
    map_tipo_para_api,
    to_float_money,
)
from tasy_insercao.domain.integracao.ports import StagingRepositoryPort, TasyRepositoryPort
from tasy_insercao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class IntegrarTransacaoCartao:
    """
    Use case de domínio: Caixa → Dia → Transação → Documento → Confirmar (FECHAR).
    Sem maquininha/caixa: só movto_cartao (status Sem Tesouraria), sem fechar/caixa.
    Idempotente por id_stone (PG status=5/8 ou movto no Oracle).
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
            # Corrige lote de ontem: status 5 no PG mas documento ausente no Tasy
            ensure_doc = getattr(self.tasy, "ensure_documento_por_id_stone", None)
            if ensure_doc is not None:
                try:
                    if ensure_doc(tx.id_stone):
                        self.staging.update_status(
                            existente[0],
                            StatusIntegracao.INTEGRADO.value,
                            "Já integrado; documento criado no reprocesso",
                        )
                        return ResultadoIntegracao(
                            id_stone=tx.id_stone,
                            status=StatusIntegracao.INTEGRADO,
                            mensagem="Já integrado; documento criado no reprocesso",
                            retryable=False,
                            nr_sequencia_pg=existente[0],
                        )
                except Exception:
                    logger.exception(
                        "Falha ao backfill documento (já integrado) | id_stone=%s",
                        tx.id_stone,
                    )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Já integrado (idempotente)",
                retryable=False,
                nr_sequencia_pg=existente[0],
            )
        if existente and existente[1] == StatusIntegracao.SEM_TESOURARIA.value:
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.SEM_TESOURARIA,
                mensagem="Já integrado sem tesouraria (idempotente)",
                retryable=False,
                nr_sequencia_pg=existente[0],
            )

        # Status 9: se ainda há movto no Oracle → só FECHAR; se já foi limpo → reintegra do zero
        if existente and existente[1] == StatusIntegracao.CONFIRMACAO_PENDENTE.value:
            if self.tasy.exists_movto_by_id_stone(tx.id_stone):
                return self._confirmar_recebimento_existente(tx, nr_seq_pg=existente[0])
            logger.info(
                "Status 9 sem movto Oracle | reintegrando do zero | id_stone=%s",
                tx.id_stone,
            )

        if self.tasy.exists_movto_by_id_stone(tx.id_stone):
            # Movto já no Oracle: se foi caminho sem caixa, mantém status 8
            obs_existente = (existente[2] if existente and len(existente) > 2 else "") or ""
            if "SEM_TESOURARIA" in obs_existente.upper() or (
                existente and existente[1] == StatusIntegracao.SEM_TESOURARIA.value
            ):
                nr = self.staging.ensure_registro(
                    tx,
                    StatusIntegracao.SEM_TESOURARIA.value,
                    "Já existia no Tasy sem tesouraria (idempotente)",
                )
                return ResultadoIntegracao(
                    id_stone=tx.id_stone,
                    status=StatusIntegracao.SEM_TESOURARIA,
                    mensagem="Já existia no Tasy sem tesouraria (idempotente)",
                    retryable=False,
                    nr_sequencia_pg=nr,
                )
            nr_pg = existente[0] if existente else self.staging.ensure_registro(
                tx,
                StatusIntegracao.PROCESSANDO.value,
                "Reprocessando confirmação",
            )
            return self._confirmar_recebimento_existente(tx, nr_seq_pg=nr_pg)

        try:
            config = None
            if hasattr(self.staging, "find_maquininha_config"):
                config = self.staging.find_maquininha_config(tx.nr_serie_maquininha)
            else:
                try:
                    config = self.staging.get_maquininha_config(tx.nr_serie_maquininha)
                except ValueError:
                    config = None

            if config is None:
                return self._integrar_sem_tesouraria(tx)

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
            nr_seq_movto = self._inserir_movto(tx, nr_seq_receb, dt_saldo, sem_tesouraria=False)

            # Ordem: documento → FECHAR. Doc sem nr_seq_caixa (FECHAR preenche).
            # Se FECHAR falhar → status 9 (reprocessável).
            self.tasy.inserir_documento(
                {
                    "nr_seq_caixa_rec": nr_seq_receb,
                    "nr_seq_movto_cartao": nr_seq_movto,
                    "dt_transacao": dt_saldo,
                    "nr_seq_trans_financ": cd_trans_fin,
                    "vl_transacao": to_float_money(tx.vl_transacao),
                }
            )

            return self._aplicar_fechar(
                tx,
                nr_seq_pg=nr_seq_pg,
                nr_seq_receb=nr_seq_receb,
                dt_str=dt_str,
                nr_seq_movto=nr_seq_movto,
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

    def _confirmar_recebimento_existente(
        self, tx: TransacaoCartao, *, nr_seq_pg: int
    ) -> ResultadoIntegracao:
        """
        Cartão/documento já no Tasy: só tenta FECHAR de novo (reprocesso status 9).
        """
        ensure_doc = getattr(self.tasy, "ensure_documento_por_id_stone", None)
        if ensure_doc is not None:
            try:
                ensure_doc(tx.id_stone)
            except Exception:
                logger.exception(
                    "Falha ao backfill documento antes do FECHAR | id_stone=%s",
                    tx.id_stone,
                )

        get_rec = getattr(self.tasy, "get_caixa_receb_para_confirmar", None)
        if get_rec is None:
            self.staging.update_status(
                nr_seq_pg,
                StatusIntegracao.INTEGRADO.value,
                "Já existia no Tasy (idempotente)",
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Já existia no Tasy (idempotente)",
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
            )

        info = get_rec(tx.id_stone)
        if not info:
            self.staging.update_status(
                nr_seq_pg,
                StatusIntegracao.INTEGRADO.value,
                "Já existia no Tasy sem caixa_receb (idempotente)",
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem="Já existia no Tasy sem caixa_receb (idempotente)",
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
            )

        if info.get("ja_fechado"):
            msg = "Recebimento já confirmado no Tasy (idempotente)"
            self.staging.update_status(nr_seq_pg, StatusIntegracao.INTEGRADO.value, msg)
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem=msg,
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
                nr_seq_caixa_receb=int(info["nr_seq_caixa_rec"]),
            )

        return self._aplicar_fechar(
            tx,
            nr_seq_pg=nr_seq_pg,
            nr_seq_receb=int(info["nr_seq_caixa_rec"]),
            dt_str=str(info["dt_recebimento"]),
            nr_seq_movto=None,
        )

    def _aplicar_fechar(
        self,
        tx: TransacaoCartao,
        *,
        nr_seq_pg: int,
        nr_seq_receb: int,
        dt_str: str,
        nr_seq_movto: int | None,
    ) -> ResultadoIntegracao:
        try:
            vl_troco = self.tasy.fechar_caixa_receb(nr_seq_receb, dt_str)
            msg = f"Transação Integrada + recebimento confirmado (troco={vl_troco})"
            self.staging.update_status(nr_seq_pg, StatusIntegracao.INTEGRADO.value, msg)
            logger.info(
                "Inserido | id_stone=%s | caixa_receb=%s | movto=%s | fechar_ok | troco=%s",
                tx.id_stone,
                nr_seq_receb,
                nr_seq_movto,
                vl_troco,
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.INTEGRADO,
                mensagem=msg,
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
                nr_seq_caixa_receb=nr_seq_receb,
            )
        except Exception as exc:
            fechar_erro = str(exc)[:300]
            deleted: dict = {}
            purge_fn = getattr(self.tasy, "purge_stone_transaction", None)
            if purge_fn is not None:
                try:
                    from tasy_insercao.infrastructure.config.settings import settings

                    purge_result = purge_fn(
                        tx.id_stone,
                        settings.TASY_NM_USUARIO,
                        allow_fechado=True,
                    )
                    deleted = purge_result.get("deleted") or {}
                    if not purge_result.get("ok"):
                        logger.warning(
                            "Purge pós-FECHAR incompleto | id_stone=%s | %s",
                            tx.id_stone,
                            purge_result.get("blocked_reason"),
                        )
                except Exception:
                    logger.exception(
                        "Falha ao purgar Oracle após FECHAR | id_stone=%s",
                        tx.id_stone,
                    )
            msg = (
                f"REINTEGRAR | FECHAR falhou | Oracle removido={deleted} | {fechar_erro}"
            )[:500]
            logger.warning(
                "Fechar_caixa_receb falhou | id_stone=%s | caixa_receb=%s | purge=%s | %s",
                tx.id_stone,
                nr_seq_receb,
                deleted,
                fechar_erro,
            )
            self.staging.update_status(
                nr_seq_pg,
                StatusIntegracao.CONFIRMACAO_PENDENTE.value,
                msg,
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.CONFIRMACAO_PENDENTE,
                mensagem=msg,
                retryable=False,  # ack — não bloqueia fila; reintegrar no portal
                nr_sequencia_pg=nr_seq_pg,
                nr_seq_caixa_receb=None,
            )

    def _integrar_sem_tesouraria(self, tx: TransacaoCartao) -> ResultadoIntegracao:
        """
        Serial sem cadastro em maquininha_stone:
        grava só movto_cartao_cr (sem saldo diário / caixa_receb / documento).
        Status 8 — Sem Tesouraria (não vai para DLQ).
        """
        dt_saldo = self._data_saldo(tx.dt_movimentacao)
        obs = (
            f"SEM_TESOURARIA | serial={tx.nr_serie_maquininha} | "
            "movto sem caixa_receb/saldo — amarrar no Tasy"
        )
        nr_seq_pg = self.staging.ensure_registro(
            tx,
            StatusIntegracao.PROCESSANDO.value,
            obs,
            cd_caixa=0,
        )
        try:
            nr_seq_movto = self._inserir_movto(tx, None, dt_saldo, sem_tesouraria=True)
            self.staging.update_status(nr_seq_pg, StatusIntegracao.SEM_TESOURARIA.value, obs)
            logger.info(
                "Inserido sem tesouraria | id_stone=%s | movto=%s | serial=%s",
                tx.id_stone,
                nr_seq_movto,
                tx.nr_serie_maquininha,
            )
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=StatusIntegracao.SEM_TESOURARIA,
                mensagem=obs,
                retryable=False,
                nr_sequencia_pg=nr_seq_pg,
            )
        except Exception as exc:
            retryable = is_retryable_error(exc)
            status = (
                StatusIntegracao.ERRO_RETRY if retryable else StatusIntegracao.ERRO_DEFINITIVO
            )
            logger.exception(
                "Falha sem tesouraria | id_stone=%s | %s",
                tx.id_stone,
                exc,
            )
            try:
                self.staging.update_status(nr_seq_pg, status.value, str(exc)[:500])
            except Exception:
                pass
            return ResultadoIntegracao(
                id_stone=tx.id_stone,
                status=status,
                mensagem=str(exc),
                retryable=retryable,
                nr_sequencia_pg=nr_seq_pg,
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
        if tipo_api == "pix":
            return dt_recebimento
        if tipo_api == "prepaid_debit":
            return dt_recebimento + timedelta(days=2)
        if tipo_api == "debit_card":
            return self.cal.add_working_days(dt_recebimento, 1)
        return dt_recebimento

    def _inserir_movto(
        self,
        tx: TransacaoCartao,
        nr_seq_caixa_rec: int | None,
        dt_recebimento: date,
        *,
        sem_tesouraria: bool,
    ) -> int:
        tipo_api = map_tipo_para_api(tx.cd_tipo_transacao.value)
        bandeira = map_stone_brand(tx.cd_bandeira)
        nr_seq_bandeira = self.staging.get_bandeira_tasy(tipo_api, bandeira)
        if nr_seq_bandeira is None and tx.cd_bandeira:
            nr_seq_bandeira = self.staging.get_bandeira_tasy(tipo_api, str(tx.cd_bandeira).strip())
        if nr_seq_bandeira is None and tipo_api == "pix":
            nr_seq_bandeira = self.staging.get_bandeira_tasy("pix", "none")
        if nr_seq_bandeira is None:
            raise ValueError(
                f"Mapeamento Tasy não encontrado para {tipo_api}/{bandeira}. "
                "Cadastre em portal → Mapeamentos (Pré-pago ≠ Débito)."
            )

        vl = to_float_money(tx.vl_transacao)
        dt_venc = self._calcular_vencimento(tipo_api, dt_recebimento)
        ds_obs = f"Maquininha - {tx.nr_serie_maquininha} | ID stone - {tx.id_stone}"
        if sem_tesouraria:
            ds_obs = f"SEM_TESOURARIA | {ds_obs}"
        if tipo_api == "pix":
            ds_obs = f"PIX | {ds_obs}"
        elif tipo_api == "prepaid_debit":
            ds_obs = f"PREPAGO | {ds_obs}"
        parcelada = tx.ie_transacao_parcelada or tx.qt_parcelas > 1

        if tipo_api == "credit_card":
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "C", 72, 2
        elif tipo_api == "prepaid_debit":
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "C", 72, 2
        elif is_debito_tasy(tipo_api):
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "D", 73, 1
        else:
            ie_tipo, nr_seq_trans_caixa, nr_seq_forma_pagto = "D", 73, 1

        if parcelada and tipo_api == "credit_card" and not sem_tesouraria:
            return self.tasy.inserir_movto_cartao_parcelado(
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

        params = {
            "ie_tipo_cartao": ie_tipo,
            "dt_transacao": dt_recebimento,
            "vl_transacao": vl,
            "ds_observacao": ds_obs,
            "nr_seq_bandeira": nr_seq_bandeira,
            "nr_autorizacao": tx.cd_autorizacao or "",
            "nr_seq_forma_pagto": nr_seq_forma_pagto,
            "nr_seq_trans_caixa": nr_seq_trans_caixa,
            "dt_primeira_parcela": dt_venc,
        }
        if sem_tesouraria:
            inserir = getattr(self.tasy, "inserir_movto_cartao_sem_tesouraria", None)
            if inserir is None:
                raise RuntimeError("TasyRepository sem inserir_movto_cartao_sem_tesouraria")
            return inserir(params)

        params["nr_seq_caixa_rec"] = nr_seq_caixa_rec
        return self.tasy.inserir_movto_cartao(params)

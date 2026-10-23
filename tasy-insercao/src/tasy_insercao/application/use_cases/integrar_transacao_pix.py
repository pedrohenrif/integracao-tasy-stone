from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tasy_insercao.application.use_cases.integrar_transacao_cartao import IntegrarTransacaoCartao
from tasy_insercao.domain.integracao.models import (
    ResultadoIntegracao,
    StatusIntegracao,
    TipoTransacaoCartao,
    TransacaoCartao,
    TransacaoPix,
)
from tasy_insercao.domain.integracao.ports import StagingRepositoryPort, TasyRepositoryPort
from tasy_insercao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

_TZ_BRT = ZoneInfo("America/Sao_Paulo")


def datetime_pix_para_caixa(dt: datetime) -> datetime:
    """Converte horário Stone PIX (UTC, com ou sem tz) para America/Sao_Paulo.

    Payload antigo chega naive em UTC; created_at da conciliação vem +00:00.
    PIX 21:37 BRT = 00:37 UTC do dia seguinte — sem isto o caixa vira D+1.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ_BRT)


def pix_para_cartao_tasy(tx: TransacaoPix) -> TransacaoCartao:
    """
    Adapta PIX para o fluxo Tasy.
    Tipo staging = pix (filtro no painel); insert Tasy = débito (ie_tipo=D, vencimento no dia).
    cd_autorizacao recebe o e2e_id quando disponível.
    """
    dt_brt = datetime_pix_para_caixa(tx.dt_movimentacao)
    return TransacaoCartao(
        id_stone=tx.id_stone,
        vl_transacao=tx.vl_transacao,
        dt_movimentacao=dt_brt,
        nr_serie_maquininha=tx.nr_serie_maquininha,
        cd_autorizacao=tx.e2e_id,
        qt_parcelas=1,
        ie_transacao_parcelada=False,
        cd_tipo_transacao=TipoTransacaoCartao.PIX,
        cd_bandeira=None,
        stone_code=tx.stone_code,
        reference_date=dt_brt.strftime("%Y-%m-%d"),
    )


class IntegrarTransacaoPix:
    """
    Use case PIX: reutiliza Caixa → Dia → Transação (regra débito do GA111),
    mantendo fila e contrato separados do cartão.
    """

    def __init__(self, staging: StagingRepositoryPort, tasy: TasyRepositoryPort) -> None:
        self.staging = staging
        self.tasy = tasy
        self._cartao = IntegrarTransacaoCartao(staging, tasy)

    def execute(self, tx: TransacaoPix) -> ResultadoIntegracao:
        logger.info(
            "Consumido | pix | id_stone=%s | e2e=%s | terminal=%s",
            tx.id_stone,
            tx.e2e_id,
            tx.nr_serie_maquininha,
        )
        adaptado = pix_para_cartao_tasy(tx)
        resultado = self._cartao.execute(adaptado)

        if resultado.nr_sequencia_pg and resultado.status == StatusIntegracao.INTEGRADO:
            try:
                self.staging.update_status(
                    resultado.nr_sequencia_pg,
                    StatusIntegracao.INTEGRADO.value,
                    f"PIX Integrado | e2e={tx.e2e_id or '-'}",
                )
            except Exception:
                pass

        return resultado.model_copy(
            update={"fluxo": "pix", "mensagem": f"[pix] {resultado.mensagem}"}
        )

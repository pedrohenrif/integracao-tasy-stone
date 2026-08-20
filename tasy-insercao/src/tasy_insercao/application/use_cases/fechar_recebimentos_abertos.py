from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from tasy_insercao.domain.integracao.ports import TasyRepositoryPort
from tasy_insercao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

_TZ_DEFAULT = "America/Sao_Paulo"


def data_ontem_iso(tz_name: str = _TZ_DEFAULT) -> str:
    """D-1 no fuso Brasil (YYYY-MM-DD)."""
    tz = ZoneInfo(tz_name)
    return (datetime.now(tz).date() - timedelta(days=1)).isoformat()


def fechar_recebimentos_abertos_stone(
    tasy: TasyRepositoryPort,
    *,
    dt: date | str | None = None,
    nr_seq_caixa: int | None = None,
    tz_name: str = _TZ_DEFAULT,
) -> dict[str, Any]:
    """
    Confirma (FECHAR_CAIXA_RECEB) todos os recebimentos Stone abertos do dia.

    Compatível com unificação: vários cartões no mesmo caixa_receb → 1 FECHAR.
    Não fecha por cartão; não cria novo recebimento.
    """
    if dt is None:
        dt_str = data_ontem_iso(tz_name)
    elif isinstance(dt, date):
        dt_str = dt.isoformat()
    else:
        dt_str = str(dt).strip()[:10]

    listar = getattr(tasy, "listar_caixa_receb_abertos_stone", None)
    if listar is None:
        raise RuntimeError("TasyRepository sem listar_caixa_receb_abertos_stone")

    abertos = listar(dt_str, nr_seq_caixa=nr_seq_caixa)
    logger.info(
        "Fechar recebimentos abertos | início | date=%s | caixa=%s | qtd=%s",
        dt_str,
        nr_seq_caixa,
        len(abertos),
    )

    itens: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0

    for item in abertos:
        nr_rec = int(item["nr_seq_caixa_rec"])
        dt_rec = str(item.get("dt_recebimento") or dt_str)
        cd_trans = item.get("nr_seq_trans_financ")
        caixa = item.get("nr_seq_caixa")

        # Garante documento agregado (soma) antes do FECHAR
        upsert = getattr(tasy, "upsert_documento_agregado", None)
        if upsert is not None and cd_trans is not None:
            try:
                upsert(
                    nr_seq_caixa_rec=nr_rec,
                    nr_seq_trans_financ=int(cd_trans),
                    dt_transacao=dt_rec,
                )
            except Exception:
                logger.exception(
                    "Falha ao upsert documento antes do FECHAR | caixa_receb=%s",
                    nr_rec,
                )

        try:
            vl_troco = tasy.fechar_caixa_receb(nr_rec, dt_rec)
            ok_count += 1
            itens.append(
                {
                    "nr_seq_caixa_rec": nr_rec,
                    "nr_seq_caixa": caixa,
                    "ok": True,
                    "vl_troco": vl_troco,
                }
            )
            logger.info(
                "Fechar recebimento ok | caixa_receb=%s | caixa=%s | troco=%s",
                nr_rec,
                caixa,
                vl_troco,
            )
        except Exception as exc:
            fail_count += 1
            erro = str(exc)[:300]
            itens.append(
                {
                    "nr_seq_caixa_rec": nr_rec,
                    "nr_seq_caixa": caixa,
                    "ok": False,
                    "erro": erro,
                }
            )
            logger.warning(
                "Fechar recebimento falhou | caixa_receb=%s | caixa=%s | %s",
                nr_rec,
                caixa,
                erro,
            )

    resultado = {
        "ok": fail_count == 0,
        "date": dt_str,
        "nr_seq_caixa": nr_seq_caixa,
        "encontrados": len(abertos),
        "fechados": ok_count,
        "falhas": fail_count,
        "itens": itens,
    }
    logger.info(
        "Fechar recebimentos abertos | fim | date=%s | fechados=%s | falhas=%s",
        dt_str,
        ok_count,
        fail_count,
    )
    return resultado

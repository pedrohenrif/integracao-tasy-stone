from __future__ import annotations

from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stone_extracao.application.services.data_referencia import data_ontem
from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.store.cron_cartao_state import (
    carregar_cron_enabled,
    salvar_cron_enabled,
)

logger = get_logger(__name__)

JOB_ID = "cartao_conciliacao_d1"

# Callable async que recebe reference_date YYYYMMDD
ExtracaoRunner = Callable[[str], Awaitable[object]]


def criar_scheduler_cartao(runner: ExtracaoRunner) -> AsyncIOScheduler:
    """
    Sempre cria o scheduler (para poder ligar/desligar pelo painel).
    O job inicia pausado se o estado persistido / .env estiver desabilitado.
    """
    scheduler = AsyncIOScheduler(timezone=settings.CARTAO_CRON_TZ)

    async def _job() -> None:
        reference_date = data_ontem(settings.CARTAO_CRON_TZ)
        logger.info(
            "Cron cartão D-1 | início | date=%s | tz=%s",
            reference_date,
            settings.CARTAO_CRON_TZ,
        )
        try:
            result = await runner(reference_date)
            published = getattr(result, "published_count", "?")
            logger.info(
                "Cron cartão D-1 | ok | date=%s | published=%s",
                reference_date,
                published,
            )
        except Exception:
            logger.exception("Cron cartão D-1 | falha | date=%s", reference_date)

    scheduler.add_job(
        _job,
        trigger=CronTrigger(
            hour=settings.CARTAO_CRON_HOUR,
            minute=settings.CARTAO_CRON_MINUTE,
            timezone=settings.CARTAO_CRON_TZ,
        ),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Cron cartão D-1 agendado | %02d:%02d %s | job=%s",
        settings.CARTAO_CRON_HOUR,
        settings.CARTAO_CRON_MINUTE,
        settings.CARTAO_CRON_TZ,
        JOB_ID,
    )
    return scheduler


def aplicar_estado_inicial(scheduler: AsyncIOScheduler) -> bool:
    """Pausa o job se desabilitado. Retorna enabled atual."""
    enabled = carregar_cron_enabled()
    job = scheduler.get_job(JOB_ID)
    if job is None:
        return enabled
    if enabled:
        job.resume()
        logger.info("Cron cartão D-1 | ativo")
    else:
        job.pause()
        logger.info("Cron cartão D-1 | pausado (painel/.env)")
    return enabled


def set_cron_enabled(scheduler: AsyncIOScheduler | None, enabled: bool) -> dict[str, Any]:
    enabled = salvar_cron_enabled(enabled)
    if scheduler is None:
        return status_cron(None)
    job = scheduler.get_job(JOB_ID)
    if job is not None:
        if enabled:
            job.resume()
        else:
            job.pause()
    return status_cron(scheduler)


def status_cron(scheduler: AsyncIOScheduler | None) -> dict[str, Any]:
    enabled = carregar_cron_enabled()
    next_run = None
    paused = not enabled
    if scheduler is not None:
        job = scheduler.get_job(JOB_ID)
        if job is not None:
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            paused = job.next_run_time is None

    return {
        "enabled": enabled,
        "running": bool(scheduler and scheduler.running),
        "paused": paused,
        "hour": settings.CARTAO_CRON_HOUR,
        "minute": settings.CARTAO_CRON_MINUTE,
        "timezone": settings.CARTAO_CRON_TZ,
        "job_id": JOB_ID,
        "mode": "d-1",
        "next_run_time": next_run,
        "next_date_preview": data_ontem(settings.CARTAO_CRON_TZ),
        "schedule": f"{settings.CARTAO_CRON_HOUR:02d}:{settings.CARTAO_CRON_MINUTE:02d}",
    }

from __future__ import annotations

from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stone_extracao.application.services.data_referencia import data_ontem_iso
from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.store.cron_pix_state import (
    carregar_cron_pix_enabled,
    salvar_cron_pix_enabled,
)

logger = get_logger(__name__)

JOB_ID = "pix_conciliacao_d1"

# Callable async que recebe reference_date YYYY-MM-DD
PixRunner = Callable[[str], Awaitable[object]]


def adicionar_job_pix(scheduler: AsyncIOScheduler, runner: PixRunner) -> None:
    """Registra o job PIX D-1 no mesmo scheduler do cartão."""

    async def _job() -> None:
        reference_date = data_ontem_iso(settings.CARTAO_CRON_TZ)
        logger.info(
            "Cron PIX D-1 | início | date=%s | tz=%s",
            reference_date,
            settings.CARTAO_CRON_TZ,
        )
        try:
            result = await runner(reference_date)
            status = getattr(result, "status", "?")
            msg = getattr(result, "message", "")
            logger.info(
                "Cron PIX D-1 | ok | date=%s | status=%s | %s",
                reference_date,
                status,
                msg,
            )
        except Exception:
            logger.exception("Cron PIX D-1 | falha | date=%s", reference_date)

    scheduler.add_job(
        _job,
        trigger=CronTrigger(
            hour=settings.PIX_CRON_HOUR,
            minute=settings.PIX_CRON_MINUTE,
            timezone=settings.CARTAO_CRON_TZ,
        ),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Cron PIX D-1 agendado | %02d:%02d %s | job=%s",
        settings.PIX_CRON_HOUR,
        settings.PIX_CRON_MINUTE,
        settings.CARTAO_CRON_TZ,
        JOB_ID,
    )


def aplicar_estado_inicial_pix(scheduler: AsyncIOScheduler) -> bool:
    enabled = carregar_cron_pix_enabled()
    job = scheduler.get_job(JOB_ID)
    if job is None:
        return enabled
    if enabled:
        job.resume()
    else:
        job.pause()
    logger.info("Cron PIX D-1 | estado inicial | enabled=%s", enabled)
    return enabled


def set_cron_pix_enabled(scheduler: AsyncIOScheduler | None, enabled: bool) -> dict[str, Any]:
    enabled = salvar_cron_pix_enabled(enabled)
    if scheduler is None:
        return status_cron_pix(None)
    job = scheduler.get_job(JOB_ID)
    if job is not None:
        if enabled:
            job.resume()
        else:
            job.pause()
    return status_cron_pix(scheduler)


def status_cron_pix(scheduler: AsyncIOScheduler | None) -> dict[str, Any]:
    enabled = carregar_cron_pix_enabled()
    next_run = None
    paused = None
    if scheduler is not None:
        job = scheduler.get_job(JOB_ID)
        if job is not None:
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            paused = job.next_run_time is None and not enabled
    return {
        "enabled": enabled,
        "running": bool(scheduler and scheduler.running),
        "paused": paused if paused is not None else (not enabled),
        "hour": settings.PIX_CRON_HOUR,
        "minute": settings.PIX_CRON_MINUTE,
        "timezone": settings.CARTAO_CRON_TZ,
        "job_id": JOB_ID,
        "mode": "d-1",
        "next_run_time": next_run,
        "next_date_preview": data_ontem_iso(settings.CARTAO_CRON_TZ),
        "schedule": f"{settings.PIX_CRON_HOUR:02d}:{settings.PIX_CRON_MINUTE:02d}",
        "flow": "request+webhook",
    }

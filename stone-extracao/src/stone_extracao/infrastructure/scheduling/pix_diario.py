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
JOB_ID_RETRY = "pix_conciliacao_d1_retry"
JOB_IDS = (JOB_ID, JOB_ID_RETRY)
MISFIRE_GRACE_SECONDS = 2 * 60 * 60

# Callable async que recebe reference_date YYYY-MM-DD
PixRunner = Callable[[str], Awaitable[object]]


def _slots_pix() -> list[tuple[str, int, int]]:
    return [
        (JOB_ID, settings.PIX_CRON_HOUR, settings.PIX_CRON_MINUTE),
        (JOB_ID_RETRY, settings.PIX_CRON_RETRY_HOUR, settings.PIX_CRON_RETRY_MINUTE),
    ]


def adicionar_job_pix(scheduler: AsyncIOScheduler, runner: PixRunner) -> None:
    """Registra os jobs PIX D-1 (principal + retry) no mesmo scheduler do cartão."""

    async def _job() -> None:
        reference_date = data_ontem_iso(settings.CARTAO_CRON_TZ)
        logger.info(
            "Cron PIX D-1 | início | date=%s | tz=%s | merchant=%s",
            reference_date,
            settings.CARTAO_CRON_TZ,
            settings.STONE_PIX_MERCHANT_ID,
        )
        try:
            result = await runner(reference_date)
            status = getattr(result, "status", "?")
            msg = getattr(result, "message", "")
            published = getattr(result, "published_from_body", 0)
            logger.info(
                "Cron PIX D-1 | ok | date=%s | status=%s | published_from_body=%s | %s",
                reference_date,
                status,
                published,
                msg,
            )
        except Exception:
            logger.exception("Cron PIX D-1 | falha | date=%s", reference_date)

    for job_id, hour, minute in _slots_pix():
        scheduler.add_job(
            _job,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=settings.CARTAO_CRON_TZ,
            ),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
        )
        logger.info(
            "Cron PIX D-1 agendado | %02d:%02d %s | job=%s",
            hour,
            minute,
            settings.CARTAO_CRON_TZ,
            job_id,
        )


def _set_jobs_enabled(scheduler: AsyncIOScheduler, enabled: bool) -> None:
    for job_id in JOB_IDS:
        job = scheduler.get_job(job_id)
        if job is None:
            continue
        if enabled:
            job.resume()
        else:
            job.pause()


def aplicar_estado_inicial_pix(scheduler: AsyncIOScheduler) -> bool:
    enabled = carregar_cron_pix_enabled()
    _set_jobs_enabled(scheduler, enabled)
    logger.info("Cron PIX D-1 | estado inicial | enabled=%s | jobs=%s", enabled, JOB_IDS)
    return enabled


def set_cron_pix_enabled(scheduler: AsyncIOScheduler | None, enabled: bool) -> dict[str, Any]:
    enabled = salvar_cron_pix_enabled(enabled)
    if scheduler is None:
        return status_cron_pix(None)
    _set_jobs_enabled(scheduler, enabled)
    return status_cron_pix(scheduler)


def status_cron_pix(scheduler: AsyncIOScheduler | None) -> dict[str, Any]:
    enabled = carregar_cron_pix_enabled()
    slots: list[dict[str, Any]] = []
    next_runs: list[str] = []
    if scheduler is not None:
        for job_id, hour, minute in _slots_pix():
            job = scheduler.get_job(job_id)
            nxt = job.next_run_time.isoformat() if job and job.next_run_time else None
            slots.append(
                {
                    "job_id": job_id,
                    "hour": hour,
                    "minute": minute,
                    "next_run_time": nxt,
                    "schedule": f"{hour:02d}:{minute:02d}",
                }
            )
            if nxt:
                next_runs.append(nxt)

    schedule = " + ".join(f"{h:02d}:{m:02d}" for _, h, m in _slots_pix())
    return {
        "enabled": enabled,
        "running": bool(scheduler and scheduler.running),
        "paused": not enabled,
        "hour": settings.PIX_CRON_HOUR,
        "minute": settings.PIX_CRON_MINUTE,
        "timezone": settings.CARTAO_CRON_TZ,
        "job_id": JOB_ID,
        "mode": "d-1",
        "next_run_time": min(next_runs) if next_runs else None,
        "next_date_preview": data_ontem_iso(settings.CARTAO_CRON_TZ),
        "schedule": schedule,
        "slots": slots,
        "flow": "request+webhook",
    }

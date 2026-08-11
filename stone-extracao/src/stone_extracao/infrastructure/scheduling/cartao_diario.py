from __future__ import annotations

from typing import Any, Awaitable, Callable

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
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
JOB_ID_RETRY = "cartao_conciliacao_d1_retry"
JOB_IDS = (JOB_ID, JOB_ID_RETRY)
# Se o processo estiver ocupado/reiniciando no minuto exato, ainda executa (padrão APScheduler = 1s).
MISFIRE_GRACE_SECONDS = 2 * 60 * 60

# Callable async que recebe reference_date YYYYMMDD
ExtracaoRunner = Callable[[str], Awaitable[object]]


def _on_scheduler_event(event) -> None:
    job_id = getattr(event, "job_id", "?")
    if event.code == EVENT_JOB_MISSED:
        logger.error(
            "Cron | job perdida (misfire) | job=%s | scheduled=%s",
            job_id,
            getattr(event, "scheduled_run_time", None),
        )
    elif event.code == EVENT_JOB_ERROR:
        logger.error("Cron | job erro | job=%s | %s", job_id, getattr(event, "exception", None))
    elif event.code == EVENT_JOB_EXECUTED:
        logger.info("Cron | job executada | job=%s", job_id)


def _slots_cartao() -> list[tuple[str, int, int]]:
    return [
        (JOB_ID, settings.CARTAO_CRON_HOUR, settings.CARTAO_CRON_MINUTE),
        (JOB_ID_RETRY, settings.CARTAO_CRON_RETRY_HOUR, settings.CARTAO_CRON_RETRY_MINUTE),
    ]


def criar_scheduler_cartao(runner: ExtracaoRunner) -> AsyncIOScheduler:
    """
    Sempre cria o scheduler (para poder ligar/desligar pelo painel).
    O job inicia pausado se o estado persistido / .env estiver desabilitado.
    """
    scheduler = AsyncIOScheduler(
        timezone=settings.CARTAO_CRON_TZ,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": MISFIRE_GRACE_SECONDS,
        },
    )
    scheduler.add_listener(
        _on_scheduler_event,
        EVENT_JOB_MISSED | EVENT_JOB_ERROR | EVENT_JOB_EXECUTED,
    )

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

    for job_id, hour, minute in _slots_cartao():
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
            "Cron cartão D-1 agendado | %02d:%02d %s | job=%s",
            hour,
            minute,
            settings.CARTAO_CRON_TZ,
            job_id,
        )
    return scheduler


def _set_jobs_enabled(scheduler: AsyncIOScheduler, enabled: bool) -> None:
    for job_id in JOB_IDS:
        job = scheduler.get_job(job_id)
        if job is None:
            continue
        if enabled:
            job.resume()
        else:
            job.pause()


def aplicar_estado_inicial(scheduler: AsyncIOScheduler) -> bool:
    """Pausa o job se desabilitado. Retorna enabled atual."""
    enabled = carregar_cron_enabled()
    _set_jobs_enabled(scheduler, enabled)
    logger.info("Cron cartão D-1 | estado inicial | enabled=%s | jobs=%s", enabled, JOB_IDS)
    return enabled


def set_cron_enabled(scheduler: AsyncIOScheduler | None, enabled: bool) -> dict[str, Any]:
    enabled = salvar_cron_enabled(enabled)
    if scheduler is None:
        return status_cron(None)
    _set_jobs_enabled(scheduler, enabled)
    return status_cron(scheduler)


def status_cron(scheduler: AsyncIOScheduler | None) -> dict[str, Any]:
    enabled = carregar_cron_enabled()
    slots: list[dict[str, Any]] = []
    next_runs: list[str] = []
    if scheduler is not None:
        for job_id, hour, minute in _slots_cartao():
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

    schedule = " + ".join(f"{h:02d}:{m:02d}" for _, h, m in _slots_cartao())
    return {
        "enabled": enabled,
        "running": bool(scheduler and scheduler.running),
        "paused": not enabled,
        "hour": settings.CARTAO_CRON_HOUR,
        "minute": settings.CARTAO_CRON_MINUTE,
        "timezone": settings.CARTAO_CRON_TZ,
        "job_id": JOB_ID,
        "mode": "d-1",
        "next_run_time": min(next_runs) if next_runs else None,
        "next_date_preview": data_ontem(settings.CARTAO_CRON_TZ),
        "schedule": schedule,
        "slots": slots,
    }

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tasy_insercao.infrastructure.auth.portal_acao_log import registrar_acao_log
from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.interfaces.api.deps import AdminUser

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class SchedulerToggleBody(BaseModel):
    enabled: bool


async def _stone_get(path: str) -> dict[str, Any]:
    base = settings.STONE_EXTRACAO_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"stone-extracao inacessível em {base}: {exc}",
        ) from exc
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"stone-extracao HTTP {resp.status_code}: {resp.text[:300]}",
        )
    return resp.json()


async def _stone_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    base = settings.STONE_EXTRACAO_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"stone-extracao inacessível em {base}: {exc}",
        ) from exc
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"stone-extracao HTTP {resp.status_code}: {resp.text[:300]}",
        )
    return resp.json()


@router.get("/cartao")
async def get_cron_cartao(_user: AdminUser):
    return await _stone_get("/scheduler/cartao")


@router.post("/cartao")
async def set_cron_cartao(body: SchedulerToggleBody, user: AdminUser):
    antes = await _stone_get("/scheduler/cartao")
    depois = await _stone_post("/scheduler/cartao", {"enabled": body.enabled})
    registrar_acao_log(
        user_id=user.get("nr_sequencia"),
        login=user.get("ds_login"),
        acao="scheduler_cartao_toggle",
        id_stone=None,
        antes={"enabled": antes.get("enabled")},
        depois={"enabled": depois.get("enabled")},
        obs=f"Cron cartão D-1 {'ativado' if body.enabled else 'desativado'}",
    )
    return depois


@router.get("/pix")
async def get_cron_pix(_user: AdminUser):
    return await _stone_get("/scheduler/pix")


@router.post("/pix")
async def set_cron_pix(body: SchedulerToggleBody, user: AdminUser):
    antes = await _stone_get("/scheduler/pix")
    depois = await _stone_post("/scheduler/pix", {"enabled": body.enabled})
    registrar_acao_log(
        user_id=user.get("nr_sequencia"),
        login=user.get("ds_login"),
        acao="scheduler_pix_toggle",
        id_stone=None,
        antes={"enabled": antes.get("enabled")},
        depois={"enabled": depois.get("enabled")},
        obs=f"Cron PIX D-1 {'ativado' if body.enabled else 'desativado'}",
    )
    return depois

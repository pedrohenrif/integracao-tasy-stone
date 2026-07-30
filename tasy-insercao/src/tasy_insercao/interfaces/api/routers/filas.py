from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from tasy_insercao.infrastructure.messaging.queue_stats import listar_filas
from tasy_insercao.interfaces.api.deps import CurrentUser

router = APIRouter(prefix="/api", tags=["filas"])


@router.get("/filas")
async def api_filas(_user: CurrentUser):
    try:
        return {"items": listar_filas()}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

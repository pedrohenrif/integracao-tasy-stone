from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tasy_insercao.infrastructure.auth.portal_auth import (
    AuthError,
    authenticate,
    create_access_token,
    ensure_admin_seed,
    listar_login_logs,
    registrar_login_log,
)
from tasy_insercao.interfaces.api.deps import AdminUser, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=120)


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat(sep=" ", timespec="seconds")
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    ensure_admin_seed()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        user = authenticate(body.login, body.password)
    except AuthError as exc:
        registrar_login_log(
            login=body.login,
            sucesso=False,
            user_id=None,
            ip=ip,
            user_agent=ua,
            mensagem=str(exc),
        )
        return JSONResponse({"detail": str(exc)}, status_code=401)

    token = create_access_token(user)
    registrar_login_log(
        login=user["ds_login"],
        sucesso=True,
        user_id=user["nr_sequencia"],
        ip=ip,
        user_agent=ua,
        mensagem="Login OK",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["nr_sequencia"],
            "login": user["ds_login"],
            "nome": user["ds_nome"],
            "admin": user.get("ie_admin") == "S",
        },
    }


@router.get("/me")
async def me(user: CurrentUser):
    return {
        "id": user["nr_sequencia"],
        "login": user["ds_login"],
        "nome": user["ds_nome"],
        "admin": user["ie_admin"],
    }


@router.get("/login-logs")
async def login_logs(_user: AdminUser, limit: int = Query(default=100, ge=1, le=500)):
    rows = listar_login_logs(limit)
    return {"items": [_serialize(r) for r in rows]}

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tasy_insercao.infrastructure.auth.portal_auth import (
    AuthError,
    authenticate,
    atualizar_usuario,
    create_access_token,
    criar_usuario,
    desativar_usuario,
    ensure_admin_seed,
    listar_login_logs,
    listar_usuarios,
    registrar_login_log,
)
from tasy_insercao.interfaces.api.deps import AdminUser, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=120)


class UsuarioCreateBody(BaseModel):
    login: str = Field(min_length=1, max_length=80)
    nome: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=4, max_length=120)
    admin: bool = False


class UsuarioUpdateBody(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=4, max_length=120)
    admin: bool | None = None
    ativo: bool | None = None


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


def _user_public(row: dict[str, Any]) -> dict[str, Any]:
    ser = _serialize(row)
    return {
        "id": ser["nr_sequencia"],
        "login": ser["ds_login"],
        "nome": ser["ds_nome"],
        "admin": ser.get("ie_admin") == "S",
        "ativo": ser.get("ie_ativo") == "S",
        "dt_inclusao": ser.get("dt_inclusao"),
        "dt_ultimo_login": ser.get("dt_ultimo_login"),
    }


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


@router.get("/usuarios")
async def api_listar_usuarios(_user: AdminUser):
    return {"items": [_user_public(r) for r in listar_usuarios()]}


@router.post("/usuarios")
async def api_criar_usuario(_user: AdminUser, body: UsuarioCreateBody):
    try:
        row = criar_usuario(
            login=body.login,
            nome=body.nome,
            password=body.password,
            admin=body.admin,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _user_public(row)


@router.patch("/usuarios/{user_id}")
async def api_atualizar_usuario(user_id: int, body: UsuarioUpdateBody, user: AdminUser):
    if user_id == user["nr_sequencia"] and body.ativo is False:
        raise HTTPException(status_code=400, detail="Não é permitido desativar o próprio usuário")
    if user_id == user["nr_sequencia"] and body.admin is False:
        raise HTTPException(status_code=400, detail="Não é permitido remover o próprio perfil admin")
    try:
        row = atualizar_usuario(
            user_id,
            nome=body.nome,
            password=body.password,
            admin=body.admin,
            ativo=body.ativo,
        )
    except AuthError as exc:
        status = 404 if "não encontrado" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _user_public(row)


@router.delete("/usuarios/{user_id}")
async def api_desativar_usuario(user_id: int, user: AdminUser):
    if user_id == user["nr_sequencia"]:
        raise HTTPException(status_code=400, detail="Não é permitido desativar o próprio usuário")
    try:
        row = desativar_usuario(user_id)
    except AuthError as exc:
        status = 404 if "não encontrado" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _user_public(row)

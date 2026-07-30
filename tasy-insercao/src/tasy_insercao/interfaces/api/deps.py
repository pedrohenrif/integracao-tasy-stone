from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tasy_insercao.infrastructure.auth.portal_auth import (
    AuthError,
    decode_token,
    get_user_by_id,
)

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except (AuthError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = get_user_by_id(user_id)
    if not user or user.get("ie_ativo") != "S":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")
    return {
        "nr_sequencia": user["nr_sequencia"],
        "ds_login": user["ds_login"],
        "ds_nome": user["ds_nome"],
        "ie_admin": user.get("ie_admin") == "S",
    }


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def require_admin(user: CurrentUser) -> dict[str, Any]:
    if not user.get("ie_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente admin",
        )
    return user


AdminUser = Annotated[dict[str, Any], Depends(require_admin)]

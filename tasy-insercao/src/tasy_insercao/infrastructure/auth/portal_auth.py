from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
import psycopg
from psycopg.rows import dict_row

from tasy_insercao.infrastructure.config.settings import settings


class AuthError(Exception):
    pass


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.PORTAL_JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user["nr_sequencia"]),
        "login": user["ds_login"],
        "nome": user["ds_nome"],
        "admin": user.get("ie_admin") == "S",
        "exp": expire,
    }
    return jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthError("Token inválido ou expirado") from exc


def get_user_by_login(login: str) -> dict[str, Any] | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT nr_sequencia, ds_login, ds_nome, ds_senha_hash, ie_ativo, ie_admin
            FROM portal_usuario
            WHERE LOWER(ds_login) = LOWER(%(login)s)
            """,
            {"login": login.strip()},
        )
        return cur.fetchone()


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT nr_sequencia, ds_login, ds_nome, ie_ativo, ie_admin, dt_ultimo_login
            FROM portal_usuario
            WHERE nr_sequencia = %(id)s
            """,
            {"id": user_id},
        )
        return cur.fetchone()


def registrar_login_log(
    *,
    login: str,
    sucesso: bool,
    user_id: int | None,
    ip: str | None,
    user_agent: str | None,
    mensagem: str,
) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO portal_login_log (
                nr_seq_usuario, ds_login, ie_sucesso, ds_ip, ds_user_agent, ds_mensagem
            ) VALUES (
                %(user_id)s, %(login)s, %(ok)s, %(ip)s, %(ua)s, %(msg)s
            )
            """,
            {
                "user_id": user_id,
                "login": login[:80],
                "ok": "S" if sucesso else "N",
                "ip": (ip or "")[:64] or None,
                "ua": (user_agent or "")[:255] or None,
                "msg": mensagem[:255],
            },
        )
        if sucesso and user_id:
            cur.execute(
                """
                UPDATE portal_usuario
                SET dt_ultimo_login = NOW()
                WHERE nr_sequencia = %(id)s
                """,
                {"id": user_id},
            )
        conn.commit()


def listar_login_logs(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                l.nr_sequencia,
                l.nr_seq_usuario,
                l.ds_login,
                l.ie_sucesso,
                l.ds_ip,
                l.ds_user_agent,
                l.ds_mensagem,
                l.dt_evento,
                u.ds_nome
            FROM portal_login_log l
            LEFT JOIN portal_usuario u ON u.nr_sequencia = l.nr_seq_usuario
            ORDER BY l.dt_evento DESC
            LIMIT %(limit)s
            """,
            {"limit": max(1, min(limit, 500))},
        )
        return list(cur.fetchall())


def ensure_admin_seed() -> None:
    """Cria admin padrão se a tabela estiver vazia."""
    login = settings.PORTAL_ADMIN_USER.strip()
    password = settings.PORTAL_ADMIN_PASS
    if not login or not password:
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM portal_usuario")
        n = int((cur.fetchone() or {}).get("n") or 0)
        if n > 0:
            return
        cur.execute(
            """
            INSERT INTO portal_usuario (ds_login, ds_nome, ds_senha_hash, ie_ativo, ie_admin)
            VALUES (%(login)s, %(nome)s, %(hash)s, 'S', 'S')
            """,
            {
                "login": login,
                "nome": "Administrador",
                "hash": hash_password(password),
            },
        )
        conn.commit()


def authenticate(login: str, password: str) -> dict[str, Any]:
    user = get_user_by_login(login)
    if not user or user.get("ie_ativo") != "S":
        raise AuthError("Usuário ou senha inválidos")
    if not verify_password(password, user["ds_senha_hash"]):
        raise AuthError("Usuário ou senha inválidos")
    return user

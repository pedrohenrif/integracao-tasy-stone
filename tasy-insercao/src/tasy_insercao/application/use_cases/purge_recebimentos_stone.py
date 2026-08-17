from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from tasy_insercao.domain.integracao.models import StatusIntegracao
from tasy_insercao.infrastructure.auth.portal_acao_log import registrar_acao_log
from tasy_insercao.infrastructure.config.logging import get_logger
from tasy_insercao.infrastructure.persistence.debug_queries import (
    FiltrosPainel,
    atualizar_status_registro,
    listar_registros,
    listar_registros_por_id_stones,
    listar_registros_por_ids,
)
from tasy_insercao.infrastructure.persistence.oracle import OracleDB, TasyOracleRepository

logger = get_logger(__name__)

MAX_BATCH = 100
TOKEN_TTL_SECONDS = 10 * 60
CONFIRM_PHRASE = "EXCLUIR"

# token -> payload
_PURGE_TOKENS: dict[str, dict[str, Any]] = {}


@dataclass
class PurgeRequest:
    nm_usuario: str = "stone"
    nr_sequencias: list[int] | None = None
    id_stones: list[str] | None = None
    cd_caixa: int | None = None
    data_de: date | None = None
    data_ate: date | None = None
    id_stone: str | None = None
    allow_fechado: bool = False


def _clean_usuario(raw: str | None) -> str:
    user = (raw or "").strip()
    if not user:
        raise ValueError("nm_usuario é obrigatório (ex.: stone)")
    if len(user) > 40:
        raise ValueError("nm_usuario inválido")
    return user


def _user_meta(user: dict[str, Any] | None) -> tuple[int | None, str]:
    if not user:
        return None, "sistema"
    return user.get("nr_sequencia"), str(user.get("ds_login") or "desconhecido")


def _purge_fingerprint(
    *,
    nm_usuario: str,
    id_stones: list[str],
    allow_fechado: bool,
) -> str:
    raw = f"{nm_usuario}|{allow_fechado}|{','.join(sorted(id_stones))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _store_token(
    *,
    nm_usuario: str,
    id_stones: list[str],
    allow_fechado: bool,
    items: list[dict[str, Any]],
) -> str:
    # limpa expirados
    now = time.time()
    expired = [k for k, v in _PURGE_TOKENS.items() if float(v.get("expires", 0)) < now]
    for k in expired:
        _PURGE_TOKENS.pop(k, None)

    token = secrets.token_urlsafe(32)
    _PURGE_TOKENS[token] = {
        "expires": now + TOKEN_TTL_SECONDS,
        "fingerprint": _purge_fingerprint(
            nm_usuario=nm_usuario, id_stones=id_stones, allow_fechado=allow_fechado
        ),
        "nm_usuario": nm_usuario,
        "id_stones": sorted(id_stones),
        "allow_fechado": bool(allow_fechado),
        "items": items,
    }
    return token


def _pop_valid_token(
    token: str,
    *,
    nm_usuario: str,
    id_stones: list[str],
    allow_fechado: bool,
) -> dict[str, Any]:
    payload = _PURGE_TOKENS.pop(token, None)
    if not payload:
        raise ValueError("Token de confirmação inválido ou já usado. Faça o preview de novo.")
    if float(payload.get("expires", 0)) < time.time():
        raise ValueError("Token de confirmação expirado. Faça o preview de novo.")
    expected = _purge_fingerprint(
        nm_usuario=nm_usuario, id_stones=id_stones, allow_fechado=allow_fechado
    )
    if payload.get("fingerprint") != expected:
        raise ValueError(
            "Filtros do confirm não batem com o preview (usuário/ids/allow_fechado)."
        )
    return payload


def _load_staging_candidates(req: PurgeRequest) -> list[dict[str, Any]]:
    nrs = sorted({int(x) for x in (req.nr_sequencias or []) if x})
    stones = sorted({(x or "").strip() for x in (req.id_stones or []) if (x or "").strip()})
    id_filter = (req.id_stone or "").strip()

    if nrs:
        rows = listar_registros_por_ids(nrs)
    elif stones:
        rows = listar_registros_por_id_stones(stones)
    else:
        # Exige escopo mínimo para não varrer o staging inteiro
        if not id_filter and req.cd_caixa is None and req.data_de is None:
            raise ValueError(
                "Informe id_stone(s), nr_sequencias, ou caixa+data_de (escopo mínimo)."
            )
        if req.cd_caixa is not None and req.data_de is None and not id_filter:
            raise ValueError("Com cd_caixa informe também data_de (ou id_stone).")
        rows = listar_registros(
            FiltrosPainel(
                data_de=req.data_de,
                data_ate=req.data_ate,
                cd_caixa=req.cd_caixa,
                id_stone=id_filter or None,
                limit=MAX_BATCH,
                offset=0,
            )
        )

    if len(rows) > MAX_BATCH:
        raise ValueError(f"Máximo {MAX_BATCH} registros por vez (recebido {len(rows)})")
    if not rows:
        raise ValueError("Nenhum registro no staging para os filtros informados")
    return rows


def preview_purge(
    req: PurgeRequest,
    *,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nm_usuario = _clean_usuario(req.nm_usuario)
    rows = _load_staging_candidates(req)
    tasy = TasyOracleRepository(OracleDB())

    items: list[dict[str, Any]] = []
    elegiveis = 0
    bloqueados = 0
    sem_oracle = 0

    for row in rows:
        id_stone = str(row["id_stone"])
        target = tasy.preview_purge_stone(id_stone, nm_usuario)
        item: dict[str, Any] = {
            "nr_sequencia": int(row["nr_sequencia"]),
            "id_stone": id_stone,
            "cd_caixa": row.get("cd_caixa"),
            "cd_status": row.get("cd_status"),
            "vl_transacao": float(row["vl_transacao"] or 0),
            "dt_movimentacao": str(row.get("dt_movimentacao") or ""),
            "oracle": target,
            "can_purge": False,
            "blocked_reason": None,
        }
        if target is None:
            item["blocked_reason"] = "Sem movto Oracle com este usuário + ID stone"
            sem_oracle += 1
        elif target["ja_fechado"] and not req.allow_fechado:
            item["blocked_reason"] = "Confirmado (dt_fechamento) — marque permitir confirmados"
            bloqueados += 1
        else:
            item["can_purge"] = True
            elegiveis += 1
        items.append(item)

    id_stones = [i["id_stone"] for i in items]
    token = _store_token(
        nm_usuario=nm_usuario,
        id_stones=id_stones,
        allow_fechado=req.allow_fechado,
        items=items,
    )

    user_id, login = _user_meta(user)
    registrar_acao_log(
        user_id=user_id,
        login=login,
        acao="purge_preview",
        obs=(
            f"usuario={nm_usuario} | elegiveis={elegiveis} | "
            f"bloqueados={bloqueados} | sem_oracle={sem_oracle} | total={len(items)}"
        )[:500],
        depois={
            "nm_usuario": nm_usuario,
            "allow_fechado": req.allow_fechado,
            "total": len(items),
            "elegiveis": elegiveis,
        },
    )

    return {
        "confirm_token": token,
        "confirm_phrase_required": CONFIRM_PHRASE,
        "expires_in_seconds": TOKEN_TTL_SECONDS,
        "nm_usuario": nm_usuario,
        "allow_fechado": req.allow_fechado,
        "totais": {
            "total": len(items),
            "elegiveis": elegiveis,
            "bloqueados": bloqueados,
            "sem_oracle": sem_oracle,
        },
        "items": items,
        "avisos": [
            "Caixa e caixa_saldo_diario NÃO são apagados.",
            "Só apaga linhas com nm_usuario informado + ID stone na observação.",
            f"Confirme digitando {CONFIRM_PHRASE} e usando o token do preview.",
        ],
    }


def confirm_purge(
    req: PurgeRequest,
    *,
    confirm_token: str,
    confirm_phrase: str,
    user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (confirm_phrase or "").strip() != CONFIRM_PHRASE:
        raise ValueError(f'Digite exatamente "{CONFIRM_PHRASE}" para confirmar')

    nm_usuario = _clean_usuario(req.nm_usuario)
    rows = _load_staging_candidates(req)
    id_stones = [str(r["id_stone"]) for r in rows]
    _pop_valid_token(
        (confirm_token or "").strip(),
        nm_usuario=nm_usuario,
        id_stones=id_stones,
        allow_fechado=req.allow_fechado,
    )

    tasy = TasyOracleRepository(OracleDB())
    user_id, login = _user_meta(user)
    resultados: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0

    by_stone = {str(r["id_stone"]): r for r in rows}

    for id_stone in id_stones:
        row = by_stone[id_stone]
        nr = int(row["nr_sequencia"])
        try:
            result = tasy.purge_stone_transaction(
                id_stone,
                nm_usuario,
                allow_fechado=req.allow_fechado,
            )
            if not result.get("ok"):
                fail_count += 1
                resultados.append(
                    {
                        "nr_sequencia": nr,
                        "id_stone": id_stone,
                        "ok": False,
                        "blocked_reason": result.get("blocked_reason"),
                        "deleted": result.get("deleted") or {},
                    }
                )
                registrar_acao_log(
                    user_id=user_id,
                    login=login,
                    acao="purge_confirm_skip",
                    nr_seq_registro=nr,
                    id_stone=id_stone,
                    obs=str(result.get("blocked_reason") or "")[:500],
                    antes={"cd_status": row.get("cd_status")},
                )
                continue

            obs = (
                f"PURGED_BY_ADMIN | usuario={nm_usuario} | "
                f"deleted={result.get('deleted')} | por={login}"
            )[:500]
            atualizar_status_registro(nr, StatusIntegracao.PENDENTE.value, obs)
            ok_count += 1
            resultados.append(
                {
                    "nr_sequencia": nr,
                    "id_stone": id_stone,
                    "ok": True,
                    "deleted": result.get("deleted") or {},
                    "staging_status": StatusIntegracao.PENDENTE.value,
                }
            )
            registrar_acao_log(
                user_id=user_id,
                login=login,
                acao="purge_confirm",
                nr_seq_registro=nr,
                id_stone=id_stone,
                antes={"cd_status": row.get("cd_status")},
                depois={
                    "cd_status": StatusIntegracao.PENDENTE.value,
                    "deleted": result.get("deleted"),
                },
                obs=obs,
            )
        except Exception as exc:
            logger.exception("Purge falhou | id_stone=%s", id_stone)
            fail_count += 1
            resultados.append(
                {
                    "nr_sequencia": nr,
                    "id_stone": id_stone,
                    "ok": False,
                    "blocked_reason": str(exc)[:300],
                    "deleted": {},
                }
            )
            registrar_acao_log(
                user_id=user_id,
                login=login,
                acao="purge_confirm_error",
                nr_seq_registro=nr,
                id_stone=id_stone,
                obs=str(exc)[:500],
            )

    return {
        "nm_usuario": nm_usuario,
        "allow_fechado": req.allow_fechado,
        "ok": ok_count,
        "falhas": fail_count,
        "resultados": resultados,
    }

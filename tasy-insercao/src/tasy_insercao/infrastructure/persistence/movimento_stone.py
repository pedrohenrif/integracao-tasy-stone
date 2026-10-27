"""Espelho das transações Stone (CSV/XML) para o portal — fora do registro_maquininha."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from psycopg.rows import dict_row

from tasy_insercao.infrastructure.config.settings import settings
from tasy_insercao.infrastructure.persistence.debug_queries import parse_csv_ints, parse_csv_tokens


def _connect() -> psycopg.Connection:
    if not settings.POSTGRES_DB:
        raise RuntimeError("POSTGRES_* não configurado")
    return psycopg.connect(settings.postgres_url, row_factory=dict_row)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _as_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw.split("+")[0])
    except ValueError:
        return None


def _clip(value: Any, n: int) -> str | None:
    """None/vazio não pode ir para slice (`None[:240]` quebra a tela Movimentos)."""
    text = str(value or "").strip()
    return text[:n] if text else None


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    if len(raw) >= 8 and raw[:8].isdigit():
        try:
            return datetime.strptime(raw[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def item_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Monta o bind do upsert. Publicado sem motivo (caso normal) não pode estourar."""
    id_stone = str(raw.get("id_stone") or "").strip()
    origem = str(raw.get("origem") or "").strip().lower()[:10]
    if not id_stone or origem not in ("pix", "cartao"):
        return None
    dt_mov = _as_dt(raw.get("dt_movimentacao"))
    ref_date = _as_date(raw.get("reference_date"))
    if ref_date is None and dt_mov is not None:
        ref_date = dt_mov.date()
    publicado = "S" if str(raw.get("publicado") or "").upper()[:1] in ("S", "1", "T") else "N"
    return {
        "origem": origem,
        "id_stone": id_stone[:80],
        "serial": _clip(raw.get("nr_serie_maquininha"), 64),
        "vl": _as_decimal(raw.get("vl_transacao")),
        "dt": dt_mov,
        "ref": ref_date,
        "status": _clip(raw.get("status_origem"), 40),
        "operation": _clip(raw.get("operation"), 40),
        "publicado": publicado,
        "motivo": _clip(raw.get("ds_motivo"), 240),
        "source": _clip(raw.get("source"), 40),
    }


def upsert_movimentos(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    sql = """
        INSERT INTO movimento_stone (
            origem, id_stone, nr_serie_maquininha, vl_transacao, dt_movimentacao,
            reference_date, status_origem, operation, publicado, ds_motivo, source
        ) VALUES (
            %(origem)s, %(id_stone)s, %(serial)s, %(vl)s, %(dt)s,
            %(ref)s, %(status)s, %(operation)s, %(publicado)s, %(motivo)s, %(source)s
        )
        ON CONFLICT (origem, id_stone) DO UPDATE SET
            nr_serie_maquininha = EXCLUDED.nr_serie_maquininha,
            vl_transacao = COALESCE(EXCLUDED.vl_transacao, movimento_stone.vl_transacao),
            dt_movimentacao = COALESCE(EXCLUDED.dt_movimentacao, movimento_stone.dt_movimentacao),
            reference_date = COALESCE(EXCLUDED.reference_date, movimento_stone.reference_date),
            status_origem = EXCLUDED.status_origem,
            operation = EXCLUDED.operation,
            publicado = EXCLUDED.publicado,
            ds_motivo = EXCLUDED.ds_motivo,
            source = EXCLUDED.source,
            dt_atualizacao = NOW()
    """
    count = 0
    with _connect() as conn, conn.cursor() as cur:
        for raw in items:
            params = item_params(raw)
            if params is None:
                continue
            cur.execute(sql, params)
            count += 1
        conn.commit()
    return count


def where_movimentos(
    *,
    data_de: date | None = None,
    data_ate: date | None = None,
    origem: str | None = None,
    nr_serie: str | None = None,
    publicado: str | None = None,
    id_stone: str | None = None,
    vl_min: Decimal | None = None,
    vl_max: Decimal | None = None,
    casou: str | None = None,
    cd_caixa: int | str | None = None,
    tipo: str | None = None,
    bandeira: str | None = None,
    cd_status: int | str | None = None,
    obs: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """WHERE do espelho + join staging. casou=N = no arquivo e sem Integrações."""
    clauses = ["TRUE"]
    params: dict[str, Any] = {}
    if data_de:
        clauses.append("m.reference_date >= %(data_de)s")
        params["data_de"] = data_de
    if data_ate:
        clauses.append("m.reference_date <= %(data_ate)s")
        params["data_ate"] = data_ate
    if origem in ("pix", "cartao"):
        clauses.append("m.origem = %(origem)s")
        params["origem"] = origem
    if nr_serie:
        clauses.append("m.nr_serie_maquininha ILIKE %(serie)s")
        params["serie"] = f"%{nr_serie.strip()}%"
    if publicado in ("S", "N"):
        clauses.append("m.publicado = %(pub)s")
        params["pub"] = publicado
    if id_stone:
        clauses.append("m.id_stone ILIKE %(id_stone)s")
        params["id_stone"] = f"%{id_stone.strip()}%"
    if vl_min is not None:
        clauses.append("m.vl_transacao >= %(vl_min)s")
        params["vl_min"] = vl_min
    if vl_max is not None:
        clauses.append("m.vl_transacao <= %(vl_max)s")
        params["vl_max"] = vl_max
    flag = (casou or "").strip().upper()[:1]
    if flag == "S":
        clauses.append("r.nr_sequencia IS NOT NULL")
    elif flag == "N":
        clauses.append("r.nr_sequencia IS NULL")
    caixas = parse_csv_ints(cd_caixa)
    if len(caixas) == 1:
        clauses.append("COALESCE(r.cd_caixa, mq.cd_caixa) = %(cd_caixa)s")
        params["cd_caixa"] = caixas[0]
    elif len(caixas) > 1:
        clauses.append("COALESCE(r.cd_caixa, mq.cd_caixa) = ANY(%(cd_caixas)s)")
        params["cd_caixas"] = caixas
    tipos = parse_csv_tokens(tipo)
    if tipos:
        tipo_parts: list[str] = []
        outros = [t for t in tipos if t != "pix"]
        if outros:
            tipo_parts.append(
                "LOWER(COALESCE(r.cd_tipo_transacao, m.operation, '')) = ANY(%(tipos)s)"
            )
            params["tipos"] = outros
        if "pix" in tipos:
            tipo_parts.append(
                "(m.origem = 'pix' OR LOWER(COALESCE(r.cd_tipo_transacao, '')) = 'pix')"
            )
        if tipo_parts:
            clauses.append("(" + " OR ".join(tipo_parts) + ")")
    bandeiras = parse_csv_tokens(bandeira)
    if bandeiras:
        band_parts: list[str] = []
        if "elo" in bandeiras:
            band_parts.append("LOWER(COALESCE(r.cd_bandeira, '')) IN ('elo', 'ticket')")
        outras = [b for b in bandeiras if b != "elo"]
        if outras:
            band_parts.append(
                "("
                + " OR ".join(
                    f"LOWER(COALESCE(r.cd_bandeira, '')) LIKE %(bandeira_{i})s"
                    for i, _ in enumerate(outras)
                )
                + ")"
            )
            for i, band in enumerate(outras):
                params[f"bandeira_{i}"] = f"%{band}%"
        if band_parts:
            clauses.append("(" + " OR ".join(band_parts) + ")")
    status_ids = parse_csv_ints(cd_status)
    if len(status_ids) == 1:
        clauses.append("r.cd_status = %(cd_status)s")
        params["cd_status"] = status_ids[0]
    elif len(status_ids) > 1:
        clauses.append("r.cd_status = ANY(%(cd_statuses)s)")
        params["cd_statuses"] = status_ids
    if obs:
        clauses.append(
            "(COALESCE(m.ds_motivo, '') ILIKE %(obs)s "
            "OR COALESCE(r.ds_obs_processo, '') ILIKE %(obs)s)"
        )
        params["obs"] = f"%{obs.strip()}%"
    return " AND ".join(clauses), params


_FROM_JOIN = """
            FROM movimento_stone m
            LEFT JOIN registro_maquininha r ON r.id_stone = m.id_stone
            LEFT JOIN maquininha_stone mq
                ON UPPER(mq.nr_serie_maquininha) = UPPER(TRIM(m.nr_serie_maquininha))
            LEFT JOIN caixas_tasy c
                ON c.cd_caixa = COALESCE(r.cd_caixa, mq.cd_caixa)
"""


def listar_movimentos(
    *,
    data_de: date | None = None,
    data_ate: date | None = None,
    origem: str | None = None,
    nr_serie: str | None = None,
    publicado: str | None = None,
    id_stone: str | None = None,
    vl_min: Decimal | None = None,
    vl_max: Decimal | None = None,
    casou: str | None = None,
    cd_caixa: int | str | None = None,
    tipo: str | None = None,
    bandeira: str | None = None,
    cd_status: int | str | None = None,
    obs: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    where, params = where_movimentos(
        data_de=data_de,
        data_ate=data_ate,
        origem=origem,
        nr_serie=nr_serie,
        publicado=publicado,
        id_stone=id_stone,
        vl_min=vl_min,
        vl_max=vl_max,
        casou=casou,
        cd_caixa=cd_caixa,
        tipo=tipo,
        bandeira=bandeira,
        cd_status=cd_status,
        obs=obs,
    )
    params["limit"] = min(max(limit, 1), 2000)
    params["offset"] = max(offset, 0)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE m.publicado = 'S') AS publicados,
                COUNT(*) FILTER (WHERE m.publicado = 'N') AS nao_publicados,
                COUNT(*) FILTER (WHERE r.nr_sequencia IS NOT NULL) AS casaram,
                COUNT(*) FILTER (WHERE r.nr_sequencia IS NULL) AS nao_casaram,
                COALESCE(SUM(m.vl_transacao), 0) AS soma_valor,
                COALESCE(SUM(m.vl_transacao) FILTER (WHERE r.nr_sequencia IS NOT NULL), 0)
                    AS soma_casaram,
                COALESCE(SUM(m.vl_transacao) FILTER (WHERE r.nr_sequencia IS NULL), 0)
                    AS soma_nao_casaram
            {_FROM_JOIN}
            WHERE {where}
            """,
            params,
        )
        resumo = cur.fetchone() or {}
        cur.execute(
            f"""
            SELECT
                m.nr_sequencia, m.origem, m.id_stone, m.nr_serie_maquininha,
                m.vl_transacao, m.dt_movimentacao, m.reference_date,
                m.status_origem, m.operation, m.publicado, m.ds_motivo, m.source,
                r.nr_sequencia AS nr_seq_registro,
                r.cd_status,
                COALESCE(r.cd_caixa, mq.cd_caixa) AS cd_caixa,
                c.ds_caixa,
                COALESCE(r.cd_tipo_transacao, m.operation) AS cd_tipo_transacao,
                r.cd_bandeira
            {_FROM_JOIN}
            WHERE {where}
            ORDER BY m.dt_movimentacao DESC NULLS LAST, m.nr_sequencia DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
        )
        rows = list(cur.fetchall())
    return {"resumo": resumo, "items": rows}

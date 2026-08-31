from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stone_extracao.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

_STATE_PATH = Path(__file__).resolve().parent / "pix_lote_state.json"


def iso_to_ymd(iso_date: str) -> str:
    """YYYY-MM-DD -> YYYYMMDD."""
    s = (iso_date or "").strip()
    if len(s) == 8 and s.isdigit():
        return s
    return s.replace("-", "")[:8]


def ymd_to_iso(ymd: str) -> str:
    """YYYYMMDD -> YYYY-MM-DD."""
    s = (ymd or "").strip()
    if len(s) == 10 and s[4] == "-":
        return s
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"data inválida: {ymd!r}")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _carregar() -> dict[str, Any]:
    data: dict[str, Any] = {"dates": {}}
    try:
        if _STATE_PATH.is_file():
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                dates = raw.get("dates")
                data["dates"] = dates if isinstance(dates, dict) else {}
    except Exception as exc:
        logger.warning("pix_lote_state | falha ao ler: %s", exc)
    return data


def _salvar(data: dict[str, Any]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _entry(data: dict[str, Any], iso_date: str) -> dict[str, Any]:
    dates = data.setdefault("dates", {})
    entry = dates.get(iso_date)
    if not isinstance(entry, dict):
        entry = {
            "awaiting_webhook": False,
            "webhook_at": None,
            "pix_published": None,
            "cartao_triggered": False,
            "cartao_at": None,
            "cartao_published": None,
        }
        dates[iso_date] = entry
    return entry


def marcar_aguardando_webhook(iso_date: str) -> None:
    """Após solicitar extrato PIX: espera webhook (mesmo se arquivo vazio)."""
    iso = ymd_to_iso(iso_to_ymd(iso_date)) if "-" not in iso_date else iso_date[:10]
    data = _carregar()
    e = _entry(data, iso)
    e["awaiting_webhook"] = True
    e["webhook_at"] = None
    # Novo pedido: permite novo disparo de cartão quando o webhook chegar
    e["cartao_triggered"] = False
    e["cartao_at"] = None
    e["cartao_published"] = None
    _salvar(data)
    logger.info("Lote dia | aguardando webhook PIX | date=%s", iso)


def marcar_webhook_recebido(iso_date: str, *, pix_published: int = 0) -> None:
    """Webhook PIX processado (com txs ou arquivo vazio)."""
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    e = _entry(data, iso)
    e["awaiting_webhook"] = False
    e["webhook_at"] = _now_iso()
    e["pix_published"] = int(pix_published)
    _salvar(data)
    logger.info(
        "Lote dia | webhook PIX ok | date=%s | pix_published=%s",
        iso,
        pix_published,
    )


def reservar_disparo_cartao(iso_date: str) -> bool:
    """
    Reserva o disparo de cartão para a data (uma vez).
    True = este caller deve publicar o cartão agora.
    """
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    e = _entry(data, iso)
    if e.get("cartao_triggered"):
        logger.info("Lote dia | cartão já disparado | date=%s", iso)
        return False
    e["cartao_triggered"] = True
    e["cartao_at"] = _now_iso()
    _salvar(data)
    logger.info("Lote dia | reservou disparo cartão | date=%s", iso)
    return True


def liberar_disparo_cartao(iso_date: str) -> None:
    """Libera reserva após falha para permitir retry (webhook/cron)."""
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    e = _entry(data, iso)
    e["cartao_triggered"] = False
    e["cartao_at"] = None
    e["cartao_published"] = None
    _salvar(data)
    logger.info("Lote dia | liberou disparo cartão (retry) | date=%s", iso)


def registrar_cartao_publicado(iso_date: str, published: int | None) -> None:
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    e = _entry(data, iso)
    e["cartao_triggered"] = True
    e["cartao_at"] = e.get("cartao_at") or _now_iso()
    e["cartao_published"] = published
    _salvar(data)


def precisa_fallback_cartao(iso_date: str) -> bool:
    """Cron fallback: webhook ainda não disparou cartão."""
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    e = _entry(data, iso)
    if e.get("cartao_triggered"):
        return False
    return True


def status_lote(iso_date: str) -> dict[str, Any]:
    iso = iso_date[:10] if iso_date and "-" in iso_date else ymd_to_iso(iso_to_ymd(iso_date))
    data = _carregar()
    return dict(_entry(data, iso))


def encontrar_iso_aguardando() -> str | None:
    """Se houver exatamente 1 dia aguardando webhook, retorna o ISO."""
    data = _carregar()
    awaiting: list[str] = []
    for key, val in (data.get("dates") or {}).items():
        if not isinstance(val, dict):
            continue
        if val.get("awaiting_webhook") and not val.get("webhook_at"):
            awaiting.append(str(key)[:10])
    if len(awaiting) == 1:
        return awaiting[0]
    return None

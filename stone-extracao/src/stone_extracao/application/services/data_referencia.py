from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def data_ontem(tz_name: str = "America/Sao_Paulo", agora: datetime | None = None) -> str:
    """Retorna D-1 no formato YYYYMMDD no fuso informado (padrão Brasil)."""
    tz = ZoneInfo(tz_name)
    agora_local = agora.astimezone(tz) if agora is not None else datetime.now(tz)
    ontem: date = agora_local.date() - timedelta(days=1)
    return ontem.strftime("%Y%m%d")


def data_ontem_iso(tz_name: str = "America/Sao_Paulo", agora: datetime | None = None) -> str:
    """Retorna D-1 no formato YYYY-MM-DD (API PIX Stone)."""
    ymd = data_ontem(tz_name, agora)
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"

from datetime import datetime
from zoneinfo import ZoneInfo

from stone_extracao.application.services.data_referencia import data_ontem, data_ontem_iso


def test_data_ontem_sao_paulo():
    # 2026-07-20 00:30 BRT → D-1 = 20260719
    agora = datetime(2026, 7, 20, 0, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert data_ontem("America/Sao_Paulo", agora=agora) == "20260719"


def test_data_ontem_virada_de_dia_utc():
    # 2026-07-20 02:00 UTC = 2026-07-19 23:00 BRT → D-1 = 20260718
    agora = datetime(2026, 7, 20, 2, 0, tzinfo=ZoneInfo("UTC"))
    assert data_ontem("America/Sao_Paulo", agora=agora) == "20260718"


def test_data_ontem_iso():
    agora = datetime(2026, 7, 20, 0, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert data_ontem_iso("America/Sao_Paulo", agora=agora) == "2026-07-19"

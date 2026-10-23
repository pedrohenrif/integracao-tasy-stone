from datetime import date, datetime

from tasy_insercao.infrastructure.persistence.movimento_stone import item_params


def test_publicado_sem_motivo_nao_quebra_slice():
    """Cron/cartão manda ds_motivo=None nas txs publicadas — era None[:240]."""
    params = item_params(
        {
            "origem": "cartao",
            "id_stone": "39562372188930",
            "nr_serie_maquininha": "4AH60NL7Z",
            "vl_transacao": "20.000000",
            "dt_movimentacao": "2026-10-22T10:16:34",
            "reference_date": "20261022",
            "publicado": "S",
            "ds_motivo": None,
            "source": "cartao",
        }
    )
    assert params is not None
    assert params["motivo"] is None
    assert params["publicado"] == "S"
    assert params["id_stone"] == "39562372188930"
    assert params["serial"] == "4AH60NL7Z"
    assert params["ref"] == date(2026, 10, 22)
    assert params["dt"] == datetime(2026, 10, 22, 10, 16, 34)
    assert params["source"] == "cartao"


def test_fora_piloto_mantem_motivo():
    params = item_params(
        {
            "origem": "cartao",
            "id_stone": "x",
            "publicado": "N",
            "ds_motivo": "fora_piloto",
            "source": None,
        }
    )
    assert params is not None
    assert params["motivo"] == "fora_piloto"
    assert params["publicado"] == "N"
    assert params["source"] is None

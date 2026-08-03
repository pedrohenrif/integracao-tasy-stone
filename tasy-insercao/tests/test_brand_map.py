from tasy_insercao.domain.integracao.policies import (
    map_bandeira_para_local,
    map_stone_brand,
)


def test_brand_id_oficial_stone():
    assert map_stone_brand("1") == "visa"
    assert map_stone_brand("2") == "mastercard"
    assert map_stone_brand("3") == "amex"
    assert map_stone_brand("4") == "cabal"
    assert map_stone_brand("5") == "unionpay"
    assert map_stone_brand("9") == "hipercard"
    assert map_stone_brand("171") == "elo"


def test_elo_nao_e_ticket():
    assert map_stone_brand("171") != "ticket"
    assert map_bandeira_para_local("171") == 3  # Elo local
    assert map_bandeira_para_local("elo") == 3

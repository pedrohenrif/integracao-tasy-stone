from tasy_insercao.domain.integracao.policies import (
    is_debito_tasy,
    map_bandeira_para_local,
    map_stone_brand,
    map_tipo_para_api,
    map_tipo_para_local,
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


def test_debito_prepago_vira_debito_normal():
    assert map_tipo_para_api("prepaid_debit") == "debit_card"
    assert map_tipo_para_local("debit_card") == 2
    assert is_debito_tasy(map_tipo_para_api("prepaid_debit")) is True


def test_credito_prepago_permanece_prepago():
    assert map_tipo_para_api("prepaid_credit") == "prepaid_credit"
    assert map_tipo_para_local("prepaid_credit") == 6
    assert is_debito_tasy(map_tipo_para_api("prepaid_credit")) is False
    assert is_debito_tasy("credit_card") is False

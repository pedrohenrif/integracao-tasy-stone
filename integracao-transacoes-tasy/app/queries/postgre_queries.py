# PostgreSQL staging / mapeamento (espelho GA111 + upsert por id_stone)

SELECT_MAQUININHA_CONFIG = """
SELECT
    ms.nr_serie_maquininha,
    ms.cd_caixa,
    ms.cd_transacao_financeira
FROM
    maquininha_stone ms
WHERE
    ms.nr_serie_maquininha = %(nr_serie_maquininha)s
"""

SELECT_CARTAO_BANDEIRA = """
SELECT
    cd_cartao_bandeira_tasy
FROM
    mapeamento_transacoes_tasy
WHERE
    ds_tipo_transacao_api = %(ds_tipo_transacao_api)s
    AND ds_bandeira_api = %(ds_bandeira_api)s
"""

SELECT_TRANSACAO_SEM_BANDEIRA = """
SELECT
    cd_cartao_bandeira_tasy
FROM
    mapeamento_transacoes_tasy
WHERE
    ds_tipo_transacao_api = %(ds_tipo_transacao_api)s
    AND ds_bandeira_api = 'none'
"""

SELECT_REGISTRO_POR_ID_STONE = """
SELECT
    nr_sequencia,
    cd_status,
    ds_obs_processo
FROM
    registro_maquininha
WHERE
    id_stone = %(id_stone)s
LIMIT 1
"""

UPSERT_REGISTRO_MAQUININHA = """
INSERT INTO registro_maquininha (
    nr_serie_maquininha,
    cd_caixa,
    dt_movimentacao,
    cd_autorizacao,
    vl_transacao,
    id_stone,
    cd_tipo_transacao,
    cd_bandeira,
    qt_parcelas,
    ie_transacao_parcelada,
    cd_status,
    ds_obs_processo
) VALUES (
    %(nr_serie_maquininha)s,
    %(cd_caixa)s,
    %(dt_movimentacao)s,
    %(cd_autorizacao)s,
    %(vl_transacao)s,
    %(id_stone)s,
    %(cd_tipo_transacao)s,
    %(cd_bandeira)s,
    %(qt_parcelas)s,
    %(ie_transacao_parcelada)s,
    %(cd_status)s,
    %(ds_obs_processo)s
)
ON CONFLICT (id_stone) DO UPDATE SET
    nr_serie_maquininha = EXCLUDED.nr_serie_maquininha,
    cd_caixa = EXCLUDED.cd_caixa,
    dt_movimentacao = EXCLUDED.dt_movimentacao,
    cd_autorizacao = EXCLUDED.cd_autorizacao,
    vl_transacao = EXCLUDED.vl_transacao,
    cd_tipo_transacao = EXCLUDED.cd_tipo_transacao,
    cd_bandeira = EXCLUDED.cd_bandeira,
    qt_parcelas = EXCLUDED.qt_parcelas,
    ie_transacao_parcelada = EXCLUDED.ie_transacao_parcelada
WHERE registro_maquininha.cd_status NOT IN (5)
RETURNING nr_sequencia, cd_status
"""

# Fallback quando não há UNIQUE em id_stone
INSERT_REGISTRO_MAQUININHA = """
INSERT INTO registro_maquininha (
    nr_serie_maquininha,
    cd_caixa,
    dt_movimentacao,
    cd_autorizacao,
    vl_transacao,
    id_stone,
    cd_tipo_transacao,
    cd_bandeira,
    qt_parcelas,
    ie_transacao_parcelada,
    cd_status,
    ds_obs_processo
) VALUES (
    %(nr_serie_maquininha)s,
    %(cd_caixa)s,
    %(dt_movimentacao)s,
    %(cd_autorizacao)s,
    %(vl_transacao)s,
    %(id_stone)s,
    %(cd_tipo_transacao)s,
    %(cd_bandeira)s,
    %(qt_parcelas)s,
    %(ie_transacao_parcelada)s,
    %(cd_status)s,
    %(ds_obs_processo)s
)
RETURNING nr_sequencia
"""

UPDATE_STATUS_TRANSACAO = """
UPDATE registro_maquininha
SET
    cd_status = %(cd_status)s,
    ds_obs_processo = %(ds_obs_processo)s
WHERE
    nr_sequencia = %(nr_sequencia)s
"""

UPDATE_STATUS_POR_ID_STONE = """
UPDATE registro_maquininha
SET
    cd_status = %(cd_status)s,
    ds_obs_processo = %(ds_obs_processo)s
WHERE
    id_stone = %(id_stone)s
"""

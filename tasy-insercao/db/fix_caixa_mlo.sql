-- Caixa MLO (41) + maquininha PB09231X75906 → transação financeira 700
-- Rodar no Postgres da VM (staging). Não precisa criar caixa novo se 41 já existir.

INSERT INTO caixas_tasy (cd_caixa, ds_caixa) VALUES
    (41, 'Caixa MLO')
ON CONFLICT (cd_caixa) DO UPDATE SET
    ds_caixa = EXCLUDED.ds_caixa,
    dt_atualizacao = NOW();

INSERT INTO maquininha_stone (
    nr_serie_maquininha, cd_caixa, ds_maquininha, ie_status, cd_transacao_financeira
) VALUES
    ('PB09231X75906', 41, 'MLO', 'A', 700)
ON CONFLICT (nr_serie_maquininha) DO UPDATE SET
    cd_caixa = EXCLUDED.cd_caixa,
    ds_maquininha = EXCLUDED.ds_maquininha,
    ie_status = EXCLUDED.ie_status,
    cd_transacao_financeira = EXCLUDED.cd_transacao_financeira;

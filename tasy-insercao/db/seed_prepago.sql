-- Pré-pago crédito (AccountType 4) → tipo 6 Pre_pago (Tasy 25/27/28).
-- Débito pré-pago (AccountType 3) NÃO usa este mapeamento — cai em Débito (tipo 2).
-- Rode só este arquivo no Postgres de staging, ou via:
--   poetry run python -m tasy_insercao.db seed --file db/seed_prepago.sql

INSERT INTO tipos_transacoes (cd_tipo_transacao, ds_tipo_transacao) VALUES
    (6, 'Pre_pago')
ON CONFLICT (cd_tipo_transacao) DO UPDATE SET ds_tipo_transacao = EXCLUDED.ds_tipo_transacao;

INSERT INTO mapeamento_transacoes_tasy (
    nr_sequencia, cd_cartao_bandeira_tasy, cd_tipo_transacao, cd_bandeira
) VALUES
    (20, 27, 6, 1),    -- Visa pré-pago crédito → 27
    (21, 25, 6, 2),    -- Master crédito pré-pago → 25
    (22, 28, 6, 3)     -- Elo crédito pré-pago → 28
ON CONFLICT (nr_sequencia) DO UPDATE SET
    cd_cartao_bandeira_tasy = EXCLUDED.cd_cartao_bandeira_tasy,
    cd_tipo_transacao = EXCLUDED.cd_tipo_transacao,
    cd_bandeira = EXCLUDED.cd_bandeira;

SELECT setval(
    pg_get_serial_sequence('mapeamento_transacoes_tasy', 'nr_sequencia'),
    COALESCE((SELECT MAX(nr_sequencia) FROM mapeamento_transacoes_tasy), 1)
);

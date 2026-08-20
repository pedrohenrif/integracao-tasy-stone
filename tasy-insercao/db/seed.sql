-- Seed Cotolengo — dados reais do staging (bandeiras / tipos / mapeamento / caixas / maquininhas)
-- Fonte: export Postgres homolog (jul/2026) + lista TI máquina→setor (jul/2026)
--
-- Setor → cd_caixa:
--   Roupas / Roupas II → 11 | Móveis → 12 | Tmkt → 13 | Recepção → 14
--   Mix → 43 | Cantina → 48 | Financeiro → 16 (Caixa Central — confirmar)
--
-- ATENÇÃO: cd_transacao_financeira de Recepção / Tmkt / Financeiro está PROVISÓRIO
-- (272 / 273 / 274). Confirmar no Tasy e ajustar no portal ou no seed antes de produção.

-- ---------------------------------------------------------------------------
-- Bandeiras locais (não confundir com BrandId Stone)
-- Stone BrandId: 1=Visa 2=MC 3=Amex 4=Cabal 5=UnionPay 9=Hipercard 171=Elo
-- Aqui: 1=Visa 2=MC 3=Elo 4=Alelo 5=Amex 6=Hipercard 7=Ticket 8=Cabal 9=UnionPay
-- ---------------------------------------------------------------------------
INSERT INTO bandeiras (cd_bandeira, ds_bandeira) VALUES
    (1, 'Visa'),
    (2, 'Mastercard'),
    (3, 'Elo'),
    (4, 'Alelo'),
    (5, 'American Express'),
    (6, 'Hipercard'),
    (7, 'Ticket'),
    (8, 'Cabal'),
    (9, 'UnionPay')
ON CONFLICT (cd_bandeira) DO UPDATE SET ds_bandeira = EXCLUDED.ds_bandeira;

INSERT INTO tipos_transacoes (cd_tipo_transacao, ds_tipo_transacao) VALUES
    (1, 'Credito'),
    (2, 'Debito'),
    (3, 'Pix'),
    (4, 'Voucher'),
    (5, 'Boleto'),
    (6, 'Pre_pago')
ON CONFLICT (cd_tipo_transacao) DO UPDATE SET ds_tipo_transacao = EXCLUDED.ds_tipo_transacao;

-- ---------------------------------------------------------------------------
-- Mapeamento → cd_cartao_bandeira_tasy (nr_sequencia do Tasy)
-- tipo: 1 Credito | 2 Debito | 3 Pix | 6 Pre_pago
-- ---------------------------------------------------------------------------
INSERT INTO mapeamento_transacoes_tasy (
    nr_sequencia, cd_cartao_bandeira_tasy, cd_tipo_transacao, cd_bandeira
) VALUES
    (1,  20, 2, 1),    -- Debito Visa
    (2,  19, 1, 1),    -- Credito Visa
    (3,  21, 3, NULL), -- Pix
    (4,   7, 1, 2),    -- Credito Mastercard
    (5,   8, 2, 2),    -- Debito Mastercard
    (6,  11, 2, 3),    -- Debito Elo → Tasy 11
    (8,  10, 1, 3),    -- Credito Elo → Tasy 10 (bandeira local 3 = Elo)
    (9,  12, 1, 5),    -- Credito American Express
    (10,  9, 1, 6),    -- Credito Hipercard → Tasy 9
    -- Ticket (bandeira local 7): cadastrar no portal quando o hospital informar o ID Tasy
    -- Pré-pago (tipo 6) — códigos Tasy Cotolengo
    (20, 27, 6, 1),    -- Pre_pago Visa (crédito pré-pago) → 27
    (21, 25, 6, 2),    -- Pre_pago Mastercard (crédito pré-pago) → 25
    (22, 28, 6, 3)     -- Pre_pago Elo (crédito pré-pago) → 28
ON CONFLICT (nr_sequencia) DO UPDATE SET
    cd_cartao_bandeira_tasy = EXCLUDED.cd_cartao_bandeira_tasy,
    cd_tipo_transacao = EXCLUDED.cd_tipo_transacao,
    cd_bandeira = EXCLUDED.cd_bandeira;

SELECT setval(
    pg_get_serial_sequence('mapeamento_transacoes_tasy', 'nr_sequencia'),
    COALESCE((SELECT MAX(nr_sequencia) FROM mapeamento_transacoes_tasy), 1)
);

-- ---------------------------------------------------------------------------
-- Caixas (staging / Tasy)
-- ---------------------------------------------------------------------------
INSERT INTO caixas_tasy (cd_caixa, ds_caixa) VALUES
    (11, 'Caixa Bazar de Roupas'),
    (12, 'Caixa Bazar de Móveis'),
    (13, 'Caixa Telemarketing'),
    (14, 'Caixa Recepção'),
    (15, 'Caixa Churrasco'),
    (16, 'Caixa Central'),
    (22, 'Caixa Escola'),
    (31, 'Caixa Cartões'),
    (33, 'Caixa Vale Alimentação Assai'),
    (34, 'Caixa Bazar da Receita'),
    (40, 'Caixa Sodexo'),
    (41, 'Caixa MLO'),
    (42, 'Caixa Eventos'),
    (43, 'Caixa Bazar Mix'),
    (44, 'Caixa Bazar Especial'),
    (45, 'Caixa Programa de Alimentação Saudável'),
    (46, 'Caixa Condor'),
    (48, 'Caixa Cantina'),
    (53, 'Caixa Relacionamento PJ')
ON CONFLICT (cd_caixa) DO UPDATE SET
    ds_caixa = EXCLUDED.ds_caixa,
    dt_atualizacao = NOW();

-- ---------------------------------------------------------------------------
-- Maquininhas (export homolog + lista TI — ie_status A=ativa, I=inativa)
-- Consumer só usa ie_status = 'A'
-- ---------------------------------------------------------------------------
INSERT INTO maquininha_stone (
    nr_sequencia, nr_serie_maquininha, cd_caixa, ds_maquininha,
    ie_status, dt_registro, cd_transacao_financeira
) VALUES
    -- Lista TI (máquina → setor)
    (1,  'PB09243M78791', 48, 'Cantina',                        'A', '2025-10-28 14:39:34.979527+00', 930),
    (2,  'PB09231S72079', 48, 'Cantina',                        'A', '2025-10-28 14:39:34.979527+00', 930),
    (3,  'PB0921B473408', 11, 'Roupas',                         'A', '2025-10-29 17:16:58.528857+00', 270),
    (5,  '4AJ45HT4D',     12, 'Móveis',                         'A', '2025-11-21 12:04:38.555361+00', 269),
    (6,  'PB09243J71219', 43, 'Mix',                            'A', '2025-11-26 16:48:14.598413+00', 935),
    (24, 'PB09248T75045', 11, 'Roupas II',                      'A', NOW(), 270),
    (25, '4AJ60KJ8H',     14, 'Recepção',                       'A', NOW(), 273),  -- PROVISÓRIO trans_fin
    (26, '4AH60NH48',     13, 'Tmkt',                           'A', NOW(), 272),  -- PROVISÓRIO trans_fin
    (27, '4AH60NL7Z',     13, 'Tmkt',                           'A', NOW(), 272),  -- PROVISÓRIO trans_fin
    (28, 'PB09218373216', 13, 'Tmkt',                           'A', NOW(), 272),  -- PROVISÓRIO trans_fin
    (29, 'PB09237272550', 13, 'Tmkt',                           'A', NOW(), 272),  -- PROVISÓRIO trans_fin
    (30, 'PB4M258670984', 13, 'Tmkt',                           'A', NOW(), 272),  -- PROVISÓRIO trans_fin
    (31, 'PB09231X75906', 16, 'Financeiro',                     'A', NOW(), 274),  -- PROVISÓRIO caixa/trans_fin
    -- Homolog anterior (ainda no parque)
    (23, 'PB0921B977799', 43, 'Mix 2',                          'A', '2025-12-08 00:11:07.657585+00', 935),
    -- Churrasco (inativas)
    (4,  '4AJ46W38R',     15, 'Maquina Churrasco 2',            'I', '2025-11-03 14:50:54.028937+00', 271),
    (7,  '4AJ705K47',     15, 'Maquina Churrasco 1',            'I', '2025-12-05 11:22:26.721749+00', 271),
    (8,  '4AJ10C46U',     15, 'Maquina Churrasco 3',            'I', '2025-12-05 11:34:40.6592+00',   271),
    (9,  '4AJ46RS5G',     15, 'Maquina Churrasco 4',            'I', '2025-12-05 11:35:18.956729+00', 271),
    (10, '4AG19GK2Z',     15, 'Maquina Churrasco 5',            'I', '2025-12-05 11:35:48.253177+00', 271),
    (11, '4AJ46F160',     15, 'Maquina Churrasco 6',            'I', '2025-12-05 11:36:14.955891+00', 271),
    (12, '4AF77430E',     15, 'Maquina Churrasco 7',            'I', '2025-12-05 11:36:37.550096+00', 271),
    (13, '4AG36LP6W',     15, 'Maquina Churrasco 8',            'I', '2025-12-05 11:37:46.643585+00', 271),
    (14, '4AH55SR4C',     15, 'Maquina Churrasco 9',            'I', '2025-12-05 11:38:06.769381+00', 271),
    (15, '4AH65MG4D',     15, 'Maquina Churrasco 10',           'I', '2025-12-05 11:38:29.128703+00', 271),
    (16, '4AF83J92V',     15, 'Maquina Churrasco 11',           'I', '2025-12-05 11:38:53.44136+00',  271),
    (17, '4AJ11WC1S',     15, 'Maquina Churrasco 12',           'I', '2025-12-05 11:39:20.502508+00', 271),
    (18, '4AH978078',     15, 'Maquina Churrasco 13',           'I', '2025-12-05 11:39:42.518403+00', 271),
    (19, '4AJ65DJ8J',     15, 'Maquina Churrasco 14',           'I', '2025-12-05 11:40:02.487761+00', 271),
    (20, '4AJ46RL60',     15, 'Maquina Churrasco 15',           'I', '2025-12-05 11:40:27.815293+00', 271),
    (21, '4AJ46F18A',     15, 'Maquina Churrasco 16',           'I', '2025-12-05 11:42:13.14355+00',  271),
    (22, '4AH95WC90',     15, 'Maquina Churrasco 17',           'I', '2025-12-05 11:44:26.877497+00', 271)
ON CONFLICT (nr_serie_maquininha) DO UPDATE SET
    cd_caixa = EXCLUDED.cd_caixa,
    ds_maquininha = EXCLUDED.ds_maquininha,
    ie_status = EXCLUDED.ie_status,
    dt_registro = EXCLUDED.dt_registro,
    cd_transacao_financeira = EXCLUDED.cd_transacao_financeira;

SELECT setval(
    pg_get_serial_sequence('maquininha_stone', 'nr_sequencia'),
    COALESCE((SELECT MAX(nr_sequencia) FROM maquininha_stone), 1)
);

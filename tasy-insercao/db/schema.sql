-- Staging Postgres — alinhado ao banco Cotolengo (GA111)
-- Uso: poetry run python -m tasy_insercao.db up

CREATE TABLE IF NOT EXISTS bandeiras (
    cd_bandeira     INTEGER PRIMARY KEY,
    ds_bandeira     VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS tipos_transacoes (
    cd_tipo_transacao   INTEGER PRIMARY KEY,
    ds_tipo_transacao   VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS caixas_tasy (
    cd_caixa              INTEGER PRIMARY KEY,
    ds_caixa              VARCHAR(120) NOT NULL,
    ie_ativo              CHAR(1) NOT NULL DEFAULT 'S',
    dt_atualizacao        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- S = várias transações financeiras: só MOVTO_CARTAO_CR (sem caixa diário / caixa_receb)
ALTER TABLE caixas_tasy
    ADD COLUMN IF NOT EXISTS ie_somente_movto CHAR(1) NOT NULL DEFAULT 'N';

-- Schema Cotolengo (export homolog)
CREATE TABLE IF NOT EXISTS maquininha_stone (
    nr_sequencia                SERIAL PRIMARY KEY,
    nr_serie_maquininha         VARCHAR(64) NOT NULL UNIQUE,
    cd_caixa                    INTEGER NOT NULL REFERENCES caixas_tasy (cd_caixa),
    ds_maquininha               VARCHAR(120),
    ie_status                   CHAR(1) NOT NULL DEFAULT 'A',  -- A=ativa, I=inativa
    dt_registro                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cd_transacao_financeira     INTEGER
);

ALTER TABLE maquininha_stone
    ALTER COLUMN cd_transacao_financeira DROP NOT NULL;

-- Schema legado Cotolengo: tipo/bandeira por FK numérico → id Tasy
CREATE TABLE IF NOT EXISTS mapeamento_transacoes_tasy (
    nr_sequencia                SERIAL PRIMARY KEY,
    cd_cartao_bandeira_tasy     INTEGER NOT NULL,
    cd_tipo_transacao           INTEGER NOT NULL REFERENCES tipos_transacoes (cd_tipo_transacao),
    cd_bandeira                 INTEGER REFERENCES bandeiras (cd_bandeira)
);

CREATE TABLE IF NOT EXISTS registro_maquininha (
    nr_sequencia                SERIAL PRIMARY KEY,
    nr_serie_maquininha         VARCHAR(64) NOT NULL,
    cd_caixa                    INTEGER,
    dt_movimentacao             TIMESTAMP NOT NULL,
    cd_autorizacao              VARCHAR(80),
    vl_transacao                NUMERIC(15, 2) NOT NULL,
    id_stone                    VARCHAR(80) NOT NULL,
    cd_tipo_transacao           VARCHAR(40),
    cd_bandeira                 VARCHAR(40),
    qt_parcelas                 INTEGER NOT NULL DEFAULT 1,
    ie_transacao_parcelada      CHAR(1) NOT NULL DEFAULT 'N',
    cd_status                   INTEGER NOT NULL DEFAULT 1,
    ds_obs_processo             VARCHAR(500),
    dt_inclusao                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dt_atualizacao              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_registro_id_stone UNIQUE (id_stone)
);

CREATE INDEX IF NOT EXISTS idx_registro_status_dt
    ON registro_maquininha (cd_status, dt_movimentacao);

CREATE INDEX IF NOT EXISTS idx_registro_terminal_dt
    ON registro_maquininha (nr_serie_maquininha, dt_movimentacao);

-- Cartão internacional (XML Stone <International>)
ALTER TABLE registro_maquininha
    ADD COLUMN IF NOT EXISTS ie_internacional CHAR(1);

-- Espelho Stone (CSV/XML) no portal, mesmo o que não entra em registro_maquininha / Tasy
CREATE TABLE IF NOT EXISTS movimento_stone (
    nr_sequencia            SERIAL PRIMARY KEY,
    origem                  VARCHAR(10) NOT NULL,
    id_stone                VARCHAR(80) NOT NULL,
    nr_serie_maquininha     VARCHAR(64),
    vl_transacao            NUMERIC(15, 2),
    dt_movimentacao         TIMESTAMP,
    reference_date          DATE,
    status_origem           VARCHAR(40),
    operation               VARCHAR(40),
    publicado               CHAR(1) NOT NULL DEFAULT 'N',
    ds_motivo               VARCHAR(240),
    source                  VARCHAR(40),
    dt_inclusao             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dt_atualizacao          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_movimento_stone_origem_id UNIQUE (origem, id_stone)
);

CREATE INDEX IF NOT EXISTS idx_movimento_stone_ref
    ON movimento_stone (reference_date, origem);

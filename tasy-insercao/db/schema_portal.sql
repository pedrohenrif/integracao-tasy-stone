-- Portal de controle (usuários + logs de login)

CREATE TABLE IF NOT EXISTS portal_usuario (
    nr_sequencia        SERIAL PRIMARY KEY,
    ds_login            VARCHAR(80) NOT NULL UNIQUE,
    ds_nome             VARCHAR(120) NOT NULL,
    ds_senha_hash       VARCHAR(255) NOT NULL,
    ie_ativo            CHAR(1) NOT NULL DEFAULT 'S',
    ie_admin            CHAR(1) NOT NULL DEFAULT 'N',
    dt_inclusao         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dt_ultimo_login     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS portal_login_log (
    nr_sequencia        SERIAL PRIMARY KEY,
    nr_seq_usuario      INTEGER REFERENCES portal_usuario (nr_sequencia),
    ds_login            VARCHAR(80) NOT NULL,
    ie_sucesso          CHAR(1) NOT NULL,
    ds_ip               VARCHAR(64),
    ds_user_agent       VARCHAR(255),
    ds_mensagem         VARCHAR(255),
    dt_evento           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_login_log_dt
    ON portal_login_log (dt_evento DESC);

CREATE INDEX IF NOT EXISTS idx_portal_login_log_user
    ON portal_login_log (nr_seq_usuario, dt_evento DESC);

-- Auditoria de ações do portal (reprocessar / editar registro)
CREATE TABLE IF NOT EXISTS portal_acao_log (
    nr_sequencia        SERIAL PRIMARY KEY,
    nr_seq_usuario      INTEGER REFERENCES portal_usuario (nr_sequencia),
    ds_login            VARCHAR(80) NOT NULL,
    ds_acao             VARCHAR(80) NOT NULL,
    nr_seq_registro     INTEGER,
    id_stone            VARCHAR(80),
    ds_antes            JSONB,
    ds_depois           JSONB,
    ds_obs              VARCHAR(500),
    dt_evento           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_acao_log_dt
    ON portal_acao_log (dt_evento DESC);

CREATE INDEX IF NOT EXISTS idx_portal_acao_log_registro
    ON portal_acao_log (nr_seq_registro, dt_evento DESC);

CREATE INDEX IF NOT EXISTS idx_portal_acao_log_stone
    ON portal_acao_log (id_stone, dt_evento DESC);

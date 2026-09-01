# Oracle — selects
SELECT_EXISTENCIA_CAIXA_SALDO_DIARIO = """
SELECT
    nr_sequencia
FROM
    caixa_saldo_diario
WHERE
    nr_seq_caixa = :nr_seq_caixa
    AND dt_saldo = TO_DATE(:dt_saldo, 'YYYY-MM-DD')
"""

# Um recebimento Stone aberto por saldo diário (caixa + dia).
# Todas as maquininhas do caixa compartilham o mesmo caixa_receb.
SELECT_CAIXA_RECEB_ABERTO_STONE = """
SELECT nr_sequencia FROM (
    SELECT cr.nr_sequencia
    FROM caixa_receb cr
    WHERE cr.nr_seq_saldo_caixa = :nr_seq_saldo_caixa
      AND cr.nm_usuario = 'stone'
      AND cr.dt_fechamento IS NULL
    ORDER BY cr.nr_sequencia
) WHERE ROWNUM = 1
"""

# Recebimentos Stone abertos no mesmo saldo diário (caixa+dia).
SELECT_CAIXA_RECEB_ABERTOS_STONE_POR_SALDO = """
SELECT
    cr.nr_sequencia,
    TO_CHAR(cr.dt_recebimento, 'YYYY-MM-DD') AS dt_recebimento
FROM caixa_receb cr
WHERE cr.nr_seq_saldo_caixa = :nr_seq_saldo_caixa
  AND cr.nm_usuario = 'stone'
  AND cr.dt_fechamento IS NULL
ORDER BY cr.nr_sequencia
"""

# Recebimentos Stone abertos de um dia (confirmação diferida pós-lote).
# :nr_seq_caixa opcional — None fecha todos os caixas do dia.
SELECT_CAIXA_RECEB_ABERTOS_STONE_POR_DATA = """
SELECT
    cr.nr_sequencia,
    TO_CHAR(cr.dt_recebimento, 'YYYY-MM-DD') AS dt_recebimento,
    csd.nr_seq_caixa,
    cr.nr_seq_trans_financ
FROM caixa_receb cr
JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
WHERE cr.nm_usuario = 'stone'
  AND cr.dt_fechamento IS NULL
  AND TRUNC(cr.dt_recebimento) = TO_DATE(:dt_recebimento, 'YYYY-MM-DD')
  AND (:nr_seq_caixa IS NULL OR csd.nr_seq_caixa = :nr_seq_caixa)
ORDER BY csd.nr_seq_caixa, cr.nr_sequencia
"""

SELECT_SOMA_MOVTO_POR_CAIXA_RECEB = """
SELECT NVL(SUM(m.vl_transacao), 0)
FROM movto_cartao_cr m
WHERE m.nr_seq_caixa_rec = :nr_seq_caixa_rec
  AND m.dt_cancelamento IS NULL
"""

# 1 doc agregado Stone por recebimento (nr_seq_movto_cartao NULL).
# NAO filtrar nr_seq_lote IS NULL: apos FECHAR o Tasy preenche o lote e o
# upsert antigo criava um 2o documento (valor dobrado na tela).
SELECT_DOC_AGREGADO_POR_CAIXA_RECEB = """
SELECT nr_sequencia FROM (
    SELECT d.nr_sequencia
    FROM movto_trans_financ d
    WHERE d.nr_seq_caixa_rec = :nr_seq_caixa_rec
      AND LOWER(d.nm_usuario) = 'stone'
      AND d.nr_seq_movto_cartao IS NULL
    ORDER BY d.nr_sequencia
) WHERE ROWNUM = 1
"""

SELECT_DOCS_AGREGADOS_EXTRA_POR_CAIXA_RECEB = """
SELECT d.nr_sequencia
FROM movto_trans_financ d
WHERE d.nr_seq_caixa_rec = :nr_seq_caixa_rec
  AND LOWER(d.nm_usuario) = 'stone'
  AND d.nr_seq_movto_cartao IS NULL
  AND d.nr_sequencia <> :nr_seq_doc_keep
ORDER BY d.nr_sequencia
"""

SELECT_QTD_MOVTO_POR_CAIXA_RECEB = """
SELECT COUNT(*)
FROM movto_cartao_cr m
WHERE m.nr_seq_caixa_rec = :nr_seq_caixa_rec
  AND m.dt_cancelamento IS NULL
"""

SELECT_CAIXA_DE_RECEB = """
SELECT csd.nr_seq_caixa
FROM caixa_receb cr
JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
WHERE cr.nr_sequencia = :nr_seq_caixa_rec
"""

SELECT_CAIXA_RECEB_TRANS_E_DATA = """
SELECT
    nr_seq_trans_financ,
    dt_recebimento,
    CASE WHEN dt_fechamento IS NULL THEN 'N' ELSE 'S' END AS ja_fechado
FROM caixa_receb
WHERE nr_sequencia = :nr_seq_caixa_rec
"""

SELECT_MOVTO_POR_ID_STONE = """
SELECT
    nr_sequencia
FROM
    movto_cartao_cr
WHERE
    ds_observacao LIKE :ds_observacao
    AND ROWNUM = 1
"""

# Movto com caixa_receb sem documento (falha no FECHAR / parcial).
SELECT_MOVTO_SEM_DOCUMENTO_POR_ID_STONE = """
SELECT
    m.nr_sequencia,
    m.nr_seq_caixa_rec,
    m.vl_transacao,
    m.dt_transacao,
    cr.nr_seq_saldo_caixa,
    cr.nr_seq_trans_financ,
    csd.nr_seq_caixa
FROM movto_cartao_cr m
JOIN caixa_receb cr ON cr.nr_sequencia = m.nr_seq_caixa_rec
JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
WHERE m.ds_observacao LIKE :ds_observacao
  AND NOT EXISTS (
      SELECT 1
      FROM movto_trans_financ d
      WHERE d.nr_seq_movto_cartao = m.nr_sequencia
         OR (
              d.nr_seq_caixa_rec = m.nr_seq_caixa_rec
          AND d.nr_seq_movto_cartao IS NULL
         )
  )
  AND ROWNUM = 1
"""

# Para reprocessar só a confirmação (FECHAR), sem reinserir cartão/documento.
SELECT_CAIXA_RECEB_PARA_CONFIRMAR = """
SELECT
    cr.nr_sequencia,
    TO_CHAR(cr.dt_recebimento, 'YYYY-MM-DD') AS dt_recebimento,
    CASE WHEN cr.dt_fechamento IS NULL THEN 'N' ELSE 'S' END AS ja_fechado
FROM movto_cartao_cr m
JOIN caixa_receb cr ON cr.nr_sequencia = m.nr_seq_caixa_rec
WHERE m.ds_observacao LIKE :ds_observacao
  AND ROWNUM = 1
"""

# Oracle — inserts (espelho GA111)
INSERT_CAIXA_SALDO_DIARIO = """
BEGIN
  abrir_caixa_saldo_diario(
    :nr_seq_caixa,
    TO_DATE(:dt_saldo, 'YYYY-MM-DD'),
    'stone',
    :id_retornado
  );
END;
"""

INSERT_CAIXA_RECEB = """
INSERT INTO caixa_receb(
    nr_sequencia,
    dt_atualizacao,
    nm_usuario,
    nr_seq_saldo_caixa,
    dt_recebimento,
    vl_especie,
    nr_seq_trans_financ,
    cd_pessoa_fisica,
    dt_atualizacao_nrec,
    nm_usuario_nrec,
    ie_tipo_receb
) VALUES (
    caixa_receb_seq.NEXTVAL,
    SYSDATE,
    'stone',
    :nr_seq_saldo_caixa,
    TO_DATE(:dt_recebimento, 'YYYY-MM-DD'),
    0,
    :nr_seq_trans_financ,
    1075,
    SYSDATE,
    'Stone',
    'R'
) RETURNING nr_sequencia INTO :id_retornado
"""

# Espelha o botão Tesouraria → Confirmar recebimento (Ctrl+F6).
# Só usar no fluxo COM caixa_receb (nunca no Sem Tesouraria).
# Chamar DEPOIS do insert de movto_trans_financ (documento) — a procedure
# confirma o recebimento; o documento da tela é o nosso INSERT.
# Se houver troco (vl_troco < 0), chama de novo com ie_troco = 'S' (padrão INTPD).
#
# CTB_ONLINE exige sessão Tasy (obter_perfil_ativo / estabelecimento).
# Sem set_cd_perfil a CTB aborta com #@DS_ERRO_W#@ (perfil 0).
CALL_FECHAR_CAIXA_RECEB = """
DECLARE
  v_troco NUMBER := 0;
BEGIN
  wheb_usuario_pck.set_nm_usuario(:nm_usuario);
  wheb_usuario_pck.set_cd_estabelecimento(:cd_estabelecimento);
  wheb_usuario_pck.set_cd_perfil(:cd_perfil);

  Fechar_caixa_receb(
    :nr_seq_caixa_rec,
    'N',
    :nm_usuario,
    v_troco,
    TO_DATE(:dt_fechamento, 'YYYY-MM-DD'),
    'S'
  );
  IF v_troco < 0 THEN
    Fechar_caixa_receb(
      :nr_seq_caixa_rec,
      'S',
      :nm_usuario,
      v_troco,
      TO_DATE(:dt_fechamento, 'YYYY-MM-DD'),
      'S'
    );
  END IF;
  :vl_troco := v_troco;
END;
"""

INSERT_MOVTO_CARTAO = """
DECLARE
  v_nr_seq_movto NUMBER;
BEGIN
    INSERT INTO movto_cartao_cr(
        nr_sequencia,
        cd_estabelecimento,
        dt_atualizacao,
        dt_transacao,
        ie_lib_caixa,
        ie_situacao,
        ie_tipo_cartao,
        nm_usuario,
        qt_parcela,
        ds_observacao,
        vl_transacao,
        nr_seq_caixa_rec,
        nr_seq_bandeira,
        nr_autorizacao,
        nr_seq_forma_pagto,
        nr_seq_trans_caixa,
        dt_liberacao
    ) VALUES (
        movto_cartao_cr_seq.NEXTVAL,
        1,
        SYSDATE,
        :dt_transacao,
        'S',
        'L',
        :ie_tipo_cartao,
        'stone',
        1,
        :ds_observacao,
        :vl_transacao,
        :nr_seq_caixa_rec,
        :nr_seq_bandeira,
        :nr_autorizacao,
        :nr_seq_forma_pagto,
        :nr_seq_trans_caixa,
        SYSDATE
    ) RETURNING nr_sequencia INTO v_nr_seq_movto;

    gerar_cartao_cr_parcela(v_nr_seq_movto, 'Stone', :dt_primeira_parcela, 'S');
    :id_retornado := v_nr_seq_movto;
END;
"""

# Sem tesouraria: movto sem caixa_receb / saldo diário (nr_seq_caixa_rec NULL)
INSERT_MOVTO_CARTAO_SEM_TESOURARIA = """
DECLARE
  v_nr_seq_movto NUMBER;
BEGIN
    INSERT INTO movto_cartao_cr(
        nr_sequencia,
        cd_estabelecimento,
        dt_atualizacao,
        dt_transacao,
        ie_lib_caixa,
        ie_situacao,
        ie_tipo_cartao,
        nm_usuario,
        qt_parcela,
        ds_observacao,
        vl_transacao,
        nr_seq_caixa_rec,
        nr_seq_bandeira,
        nr_autorizacao,
        nr_seq_forma_pagto,
        nr_seq_trans_caixa,
        dt_liberacao
    ) VALUES (
        movto_cartao_cr_seq.NEXTVAL,
        1,
        SYSDATE,
        :dt_transacao,
        'N',
        'L',
        :ie_tipo_cartao,
        'stone',
        1,
        :ds_observacao,
        :vl_transacao,
        NULL,
        :nr_seq_bandeira,
        :nr_autorizacao,
        :nr_seq_forma_pagto,
        :nr_seq_trans_caixa,
        SYSDATE
    ) RETURNING nr_sequencia INTO v_nr_seq_movto;

    gerar_cartao_cr_parcela(v_nr_seq_movto, 'Stone', :dt_primeira_parcela, 'S');
    :id_retornado := v_nr_seq_movto;
END;
"""

INSERT_MOVTO_CARTAO_PARCELADO = """
DECLARE
  v_nr_seq_movto NUMBER;
BEGIN
    INSERT INTO movto_cartao_cr(
        nr_sequencia,
        cd_estabelecimento,
        dt_atualizacao,
        dt_transacao,
        ie_lib_caixa,
        ie_situacao,
        ie_tipo_cartao,
        nm_usuario,
        ds_observacao,
        vl_transacao,
        nr_seq_caixa_rec,
        nr_seq_bandeira,
        qt_parcela,
        nr_seq_forma_pagto,
        nr_autorizacao,
        nr_seq_trans_caixa,
        dt_liberacao
    ) VALUES (
        movto_cartao_cr_seq.NEXTVAL,
        1,
        SYSDATE,
        :dt_transacao,
        'S',
        'L',
        'C',
        'stone',
        :ds_observacao,
        :vl_transacao,
        :nr_seq_caixa_rec,
        :nr_seq_bandeira,
        :qt_parcelas,
        6,
        :nr_autorizacao,
        :nr_seq_trans_caixa,
        SYSDATE
    ) RETURNING nr_sequencia INTO v_nr_seq_movto;

    gerar_cartao_cr_parcela(v_nr_seq_movto, 'Stone', :dt_primeira_parcela, 'S');
    :id_retornado := v_nr_seq_movto;
END;
"""

# Documento agregado do recebimento (1 doc = soma dos cartões).
# Sem nr_seq_movto_cartao: representa o lote, não um cartão isolado.
# Sem nr_seq_caixa / lote (FECHAR preenche na confirmação).
INSERT_MOVTO_TRANS_FINANC_AGREGADO = """
INSERT INTO movto_trans_financ(
    nr_sequencia,
    dt_transacao,
    cd_moeda,
    nr_seq_trans_financ,
    cd_pessoa_fisica,
    vl_transacao,
    dt_atualizacao,
    nm_usuario,
    nr_lote_contabil,
    ie_conciliacao,
    nr_seq_caixa_rec,
    nr_seq_movto_cartao,
    ie_rejeitado,
    ie_outros_rec,
    cd_estabelecimento
) VALUES (
    movto_trans_financ_seq.NEXTVAL,
    :dt_transacao,
    1,
    :nr_seq_trans_financ,
    1075,
    :vl_transacao,
    SYSDATE,
    'stone',
    0,
    'N',
    :nr_seq_caixa_rec,
    NULL,
    'N',
    'N',
    1
)
"""

UPDATE_DOC_AGREGADO_VALOR = """
UPDATE movto_trans_financ d
SET d.vl_transacao = :vl_transacao,
    d.nr_seq_trans_financ = :nr_seq_trans_financ,
    d.nr_seq_movto_cartao = NULL,
    d.dt_atualizacao = SYSDATE
WHERE d.nr_sequencia = :nr_seq_doc
  AND LOWER(d.nm_usuario) = 'stone'
"""

DELETE_DOC_AGREGADO_EXTRA = """
DELETE FROM movto_trans_financ d
WHERE d.nr_sequencia = :nr_seq_doc
  AND LOWER(d.nm_usuario) = 'stone'
  AND d.nr_seq_movto_cartao IS NULL
  AND d.nr_seq_caixa_rec = :nr_seq_caixa_rec
"""

# Documento legado (1:1 com cartão) — mantido para compat.
# NÃO preencher nr_seq_caixa / nr_seq_saldo_caixa / nr_seq_lote.
INSERT_MOVTO_TRANS_FINANC = """
INSERT INTO movto_trans_financ(
    nr_sequencia,
    dt_transacao,
    cd_moeda,
    nr_seq_trans_financ,
    cd_pessoa_fisica,
    vl_transacao,
    dt_atualizacao,
    nm_usuario,
    nr_lote_contabil,
    ie_conciliacao,
    nr_seq_caixa_rec,
    nr_seq_movto_cartao,
    ie_rejeitado,
    ie_outros_rec,
    cd_estabelecimento
) VALUES (
    movto_trans_financ_seq.NEXTVAL,
    :dt_transacao,
    1,
    :nr_seq_trans_financ,
    1075,
    :vl_transacao,
    SYSDATE,
    'stone',
    0,
    'N',
    :nr_seq_caixa_rec,
    :nr_seq_movto_cartao,
    'N',
    'N',
    1
)
"""

# Docs já gravados com nr_seq_caixa (bloqueiam FECHAR): libera antes de confirmar.
LIBERAR_DOC_LOTE_ANTES_FECHAR = """
UPDATE movto_trans_financ d
SET d.nr_seq_caixa = NULL,
    d.nr_seq_lote = NULL,
    d.dt_atualizacao = SYSDATE
WHERE d.nr_seq_caixa_rec = :nr_seq_caixa_rec
  AND d.nm_usuario = 'stone'
  AND d.dt_fechamento_lote IS NULL
"""

# Alinha docs Stone: transação = caixa_receb; valor = total do movto_cartao
UPDATE_DOC_STONE_TRANS_E_VALOR = """
UPDATE movto_trans_financ d
SET
    d.nr_seq_trans_financ = (
        SELECT cr.nr_seq_trans_financ
        FROM caixa_receb cr
        WHERE cr.nr_sequencia = d.nr_seq_caixa_rec
    ),
    d.vl_transacao = NVL(
        (
            SELECT m.vl_transacao
            FROM movto_cartao_cr m
            WHERE m.nr_sequencia = d.nr_seq_movto_cartao
        ),
        d.vl_transacao
    ),
    d.dt_atualizacao = SYSDATE
WHERE d.nm_usuario = 'stone'
  AND d.nr_seq_caixa_rec IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM caixa_receb cr
      WHERE cr.nr_sequencia = d.nr_seq_caixa_rec
        AND cr.nr_seq_trans_financ IS NOT NULL
  )
"""

# Corrige docs Stone já gravados sem vínculo com o cartão.
# Não preenche nr_seq_caixa (FECHAR preenche; senão vira "lote aberto").
UPDATE_DOC_STONE_VINCULO_CARTAO = """
UPDATE movto_trans_financ d
SET
    d.nr_seq_movto_cartao = (
        SELECT MAX(m.nr_sequencia)
        FROM movto_cartao_cr m
        WHERE m.nr_seq_caixa_rec = d.nr_seq_caixa_rec
    ),
    d.dt_atualizacao = SYSDATE,
    d.nm_usuario = 'stone'
WHERE d.nm_usuario = 'stone'
  AND d.nr_seq_movto_cartao IS NULL
  AND d.nr_seq_caixa_rec IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM movto_cartao_cr m
      WHERE m.nr_seq_caixa_rec = d.nr_seq_caixa_rec
  )
"""

# --- Purge admin (chave = ID stone na observação; nunca caixa / saldo diário) ---
# Preferência: nm_usuario informado. Fallback: só ID stone (FECHAR/Tasy pode alterar nm_usuario).

SELECT_PURGE_TARGET = """
SELECT
    m.nr_sequencia,
    m.nr_seq_caixa_rec,
    m.vl_transacao,
    TO_CHAR(m.dt_transacao, 'YYYY-MM-DD'),
    CASE
      WHEN cr.nr_sequencia IS NULL THEN 'N'
      WHEN cr.dt_fechamento IS NULL THEN 'N'
      ELSE 'S'
    END,
    (
      SELECT COUNT(*)
      FROM movto_trans_financ d
      WHERE d.nr_seq_movto_cartao = m.nr_sequencia
         OR (
            m.nr_seq_caixa_rec IS NOT NULL
            AND d.nr_seq_caixa_rec = m.nr_seq_caixa_rec
            AND d.nr_seq_movto_cartao IS NULL
         )
    ),
    m.nm_usuario,
    cr.nm_usuario,
    SUBSTR(m.ds_observacao, 1, 200)
FROM movto_cartao_cr m
LEFT JOIN caixa_receb cr
  ON cr.nr_sequencia = m.nr_seq_caixa_rec
WHERE m.nm_usuario = :nm_usuario
  AND UPPER(m.ds_observacao) LIKE UPPER(:ds_observacao)
  AND ROWNUM = 1
"""

SELECT_PURGE_TARGET_BY_ID = """
SELECT
    m.nr_sequencia,
    m.nr_seq_caixa_rec,
    m.vl_transacao,
    TO_CHAR(m.dt_transacao, 'YYYY-MM-DD'),
    CASE
      WHEN cr.nr_sequencia IS NULL THEN 'N'
      WHEN cr.dt_fechamento IS NULL THEN 'N'
      ELSE 'S'
    END,
    (
      SELECT COUNT(*)
      FROM movto_trans_financ d
      WHERE d.nr_seq_movto_cartao = m.nr_sequencia
         OR (
            m.nr_seq_caixa_rec IS NOT NULL
            AND d.nr_seq_caixa_rec = m.nr_seq_caixa_rec
            AND d.nr_seq_movto_cartao IS NULL
         )
    ),
    m.nm_usuario,
    cr.nm_usuario,
    SUBSTR(m.ds_observacao, 1, 200)
FROM movto_cartao_cr m
LEFT JOIN caixa_receb cr
  ON cr.nr_sequencia = m.nr_seq_caixa_rec
WHERE UPPER(m.ds_observacao) LIKE UPPER(:ds_observacao)
  AND ROWNUM = 1
"""

SELECT_PURGE_QTD_PARCELAS = """
SELECT COUNT(*)
FROM cartao_cr_parcela
WHERE nr_seq_movto = :nr_seq_movto
"""

# Desvincula só o doc ligado a ESTE movto (não mexe em docs agregados do lote).
UNLINK_PURGE_DOCS_MOVTO = """
UPDATE movto_trans_financ d
SET d.nr_seq_movto_cartao = NULL
WHERE d.nr_seq_movto_cartao = :nr_seq_movto
"""

DELETE_PURGE_DOCS_MOVTO = """
DELETE FROM movto_trans_financ d
WHERE d.nr_seq_movto_cartao = :nr_seq_movto
"""

# Docs agregados do recebimento (nr_seq_movto_cartao NULL) só se não restar movto.
DELETE_PURGE_DOCS_RECEB_ORFAOS = """
DELETE FROM movto_trans_financ d
WHERE d.nr_seq_caixa_rec = :nr_seq_caixa_rec
  AND d.nr_seq_movto_cartao IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM movto_cartao_cr m WHERE m.nr_seq_caixa_rec = :nr_seq_caixa_rec
  )
"""

DELETE_PURGE_PARCELAS = """
DELETE FROM cartao_cr_parcela
WHERE nr_seq_movto = :nr_seq_movto
"""

DELETE_PURGE_MOVTO = """
DELETE FROM movto_cartao_cr
WHERE nr_sequencia = :nr_seq_movto
  AND UPPER(ds_observacao) LIKE UPPER(:ds_observacao)
"""

DELETE_PURGE_CAIXA_RECEB = """
DELETE FROM caixa_receb cr
WHERE cr.nr_sequencia = :nr_seq_caixa_rec
  AND NOT EXISTS (
    SELECT 1 FROM movto_cartao_cr m WHERE m.nr_seq_caixa_rec = cr.nr_sequencia
  )
  AND NOT EXISTS (
    SELECT 1 FROM movto_trans_financ d WHERE d.nr_seq_caixa_rec = cr.nr_sequencia
  )
"""

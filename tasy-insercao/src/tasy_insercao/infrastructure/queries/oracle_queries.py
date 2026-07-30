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

SELECT_MOVTO_POR_ID_STONE = """
SELECT
    nr_sequencia
FROM
    movto_cartao_cr
WHERE
    ds_observacao LIKE :ds_observacao
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

# Documento: mesma transação do caixa_receb; valor = total da transação (parcelado incluso)
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
    nr_seq_saldo_caixa,
    nr_seq_caixa,
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
    :nr_seq_saldo_caixa,
    :nr_seq_caixa,
    'N',
    'N',
    1
)
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

# Corrige docs Stone já gravados sem vínculo com o cartão
UPDATE_DOC_STONE_VINCULO_CARTAO = """
UPDATE movto_trans_financ d
SET
    d.nr_seq_movto_cartao = (
        SELECT MAX(m.nr_sequencia)
        FROM movto_cartao_cr m
        WHERE m.nr_seq_caixa_rec = d.nr_seq_caixa_rec
    ),
    d.nr_seq_saldo_caixa = (
        SELECT cr.nr_seq_saldo_caixa
        FROM caixa_receb cr
        WHERE cr.nr_sequencia = d.nr_seq_caixa_rec
    ),
    d.nr_seq_caixa = (
        SELECT csd.nr_seq_caixa
        FROM caixa_receb cr
        JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
        WHERE cr.nr_sequencia = d.nr_seq_caixa_rec
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

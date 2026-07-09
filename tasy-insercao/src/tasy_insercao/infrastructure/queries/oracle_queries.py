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
    2,
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
END;
"""

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
    ie_rejeitado,
    ie_outros_rec,
    cd_estabelecimento
) VALUES (
    movto_trans_financ_seq.NEXTVAL,
    :dt_transacao,
    1,
    :nr_seq_trans_financ,
    2,
    obter_valores_caixa_rec(:nr_seq_caixa_rec, 'VCA'),
    SYSDATE,
    'stone',
    0,
    'N',
    :nr_seq_caixa_rec,
    'N',
    'N',
    1
)
"""

# Debug — integração Stone → Tasy

Guia rápido de SELECTs (Postgres staging + Oracle Tasy) e status.

---

## Documento em `MOVTO_TRANS_FINANC`

O consumer **grava** o documento após o cartão. Para a tela do Tasy:

| Campo | Valor |
|-------|--------|
| `nr_seq_caixa_rec` | PK do `caixa_receb` |
| `nr_seq_movto_cartao` | PK do `movto_cartao_cr` |
| `nr_seq_saldo_caixa` / `nr_seq_caixa` | saldo e caixa |
| `nr_seq_trans_financ` | **mesma** do `caixa_receb` (maquininha, ex. **930**) |
| `vl_transacao` | **total** da venda (parcelado = valor cheio, não parcela) |

---

## Reprocessar no portal (Erros / DLQ)

Na tela **Erros / DLQ**:

1. **Reprocessar (por linha)** — edita serial/caixa só neste registro e reenfileira (`POST /api/reprocessar/registro`). Só status 6/7.
2. **Reprocessar selecionados** — lote sem edição (`POST /api/reprocessar/selecionados`). Status 5 é ignorado.
3. **Reprocessar dia** — chama `stone-extracao` (`POST /api/reprocessar/dia`).

Auditoria: tela **Auditoria** / `GET /api/reprocessar/logs` (`portal_acao_log`).

Consumer precisa estar rodando para consumir a fila.

---

## Idempotência (não integra duas vezes)

Sim. A mesma `id_stone` **não** gera segundo movimento no Tasy:

1. **Postgres** — se `registro_maquininha.cd_status = 5`, o consumer retorna  
   `Já integrado (idempotente)` e **não** chama insert no Oracle.
2. **Oracle** — se já existe linha em `movto_cartao_cr` com  
   `ds_observacao LIKE '%ID stone - {id}%'`, marca PG como 5 e pula o insert.
3. **Unique** — `registro_maquininha.id_stone` é UNIQUE no staging.

Reprocessar a mesma data / reenviar a fila é seguro: as que já estão OK são ignoradas.

---

## Status (`registro_maquininha.cd_status`)

| Código | Nome | Significado |
|--------|------|-------------|
| 1 | Pendente | Registro criado, ainda não processado |
| 2 | Processando | Em andamento (Caixa → Dia → Transação) |
| 5 | Integrado | OK no Tasy (ou já existia — idempotente) |
| 6 | Erro + retry | Falha transitória; vai para fila retry |
| 7 | DLQ | Erro definitivo após esgotar tentativas |
| 8 | Sem Tesouraria | Movto cartão no Tasy **sem** caixa_receb/saldo (serial sem cadastro). Não vai para DLQ. |

---

## Postgres (staging local)

Banco típico: `maquina_stone` (ver `tasy-insercao/.env`).

### Resumo por status

```sql
SELECT cd_status, COUNT(*)
FROM registro_maquininha
GROUP BY 1
ORDER BY 1;
```

### Últimos registros

```sql
SELECT
    id_stone,
    nr_serie_maquininha,
    cd_caixa,
    vl_transacao,
    cd_tipo_transacao,
    cd_bandeira,
    cd_status,
    ds_obs_processo,
    dt_inclusao,
    dt_atualizacao
FROM registro_maquininha
ORDER BY dt_inclusao DESC
LIMIT 50;
```

### Só erros (DLQ / retry)

```sql
SELECT id_stone, nr_serie_maquininha, cd_status, ds_obs_processo, dt_atualizacao
FROM registro_maquininha
WHERE cd_status IN (6, 7)
ORDER BY dt_atualizacao DESC;
```

### Buscar um `id_stone`

```sql
SELECT *
FROM registro_maquininha
WHERE id_stone = 'COLE_O_ID_AQUI';
```

### Maquininhas ativas (cadastro)

```sql
SELECT nr_serie_maquininha, cd_caixa, cd_transacao_financeira, ie_status, ds_maquininha
FROM maquininha_stone
WHERE ie_status = 'A'
ORDER BY nr_serie_maquininha;
```

### Mapeamento bandeira → Tasy

```sql
SELECT
    m.nr_sequencia,
    t.ds_tipo_transacao,
    b.ds_bandeira,
    m.cd_cartao_bandeira_tasy
FROM mapeamento_transacoes_tasy m
JOIN tipos_transacoes t ON t.cd_tipo_transacao = m.cd_tipo_transacao
LEFT JOIN bandeiras b ON b.cd_bandeira = m.cd_bandeira
ORDER BY m.cd_tipo_transacao, m.cd_bandeira NULLS FIRST;
```

### Pré-pago (AccountType 3/4 Stone)

- Staging / fila: `prepaid_debit` (não vira `debit_card`)
- Tipo local: **6 = Pre_pago** → bandeiras Tasy 25/27/28 (Master/Visa/Elo Crédito Pré-Pago)
- Insert Tasy: `ie_tipo_cartao=C`, `nr_seq_forma_pagto=2`, `nr_seq_trans_caixa=72` (regras em `forma_pagto_regra` só existem como **C+forma 2**)
- Se mandar `D`+forma 1 → `ORA-20011` / mensagem 203886 (sem `tx_administracao` na regra)
- Vencimento: D+2 (conforme `qt_dias_venc` das regras Cotolengo)

### Caixas (staging)

```sql
-- Lista completa
SELECT cd_caixa, ds_caixa, ie_ativo, dt_atualizacao
FROM caixas_tasy
ORDER BY cd_caixa;

-- Um caixa
SELECT cd_caixa, ds_caixa, ie_ativo
FROM caixas_tasy
WHERE cd_caixa = 48;

-- Caixa + maquininhas ligadas
SELECT
    c.cd_caixa,
    c.ds_caixa,
    m.nr_serie_maquininha,
    m.ds_maquininha,
    m.ie_status,
    m.cd_transacao_financeira
FROM caixas_tasy c
LEFT JOIN maquininha_stone m ON m.cd_caixa = c.cd_caixa
ORDER BY c.cd_caixa, m.nr_serie_maquininha;

-- Só caixas que têm maquininha ativa
SELECT DISTINCT c.cd_caixa, c.ds_caixa
FROM caixas_tasy c
JOIN maquininha_stone m ON m.cd_caixa = c.cd_caixa AND m.ie_status = 'A'
ORDER BY c.cd_caixa;

-- Volume integrado por caixa (status 5)
SELECT
    COALESCE(r.cd_caixa, 0) AS cd_caixa,
    c.ds_caixa,
    COUNT(*) AS qtd,
    SUM(r.vl_transacao) AS total
FROM registro_maquininha r
LEFT JOIN caixas_tasy c ON c.cd_caixa = r.cd_caixa
WHERE r.cd_status = 5
GROUP BY 1, 2
ORDER BY 1;

-- Registros de um caixa
SELECT id_stone, nr_serie_maquininha, vl_transacao, cd_status, ds_obs_processo, dt_inclusao
FROM registro_maquininha
WHERE cd_caixa = 48
ORDER BY dt_inclusao DESC
LIMIT 50;
```

### Terminal sem cadastro / inativo (suspeitos de status 7)

```sql
SELECT r.id_stone, r.nr_serie_maquininha, r.cd_status, r.ds_obs_processo, m.ie_status
FROM registro_maquininha r
LEFT JOIN maquininha_stone m ON m.nr_serie_maquininha = r.nr_serie_maquininha
WHERE r.cd_status = 7
ORDER BY r.dt_atualizacao DESC;
```

### Contagem por terminal

```sql
SELECT nr_serie_maquininha, cd_status, COUNT(*)
FROM registro_maquininha
GROUP BY 1, 2
ORDER BY 1, 2;
```

---

## Oracle (Tasy homolog)

Conectar com o mesmo `ORACLE_*` do `.env`.

A marcação de origem fica em `ds_observacao`, no formato:

`Maquininha - {serial} | ID stone - {id_stone}`

### Existe movimento para um `id_stone`? (idempotência)

```sql
SELECT nr_sequencia, dt_transacao, vl_transacao, ds_observacao, nr_seq_bandeira
FROM movto_cartao_cr
WHERE ds_observacao LIKE '%ID stone - COLE_O_ID_AQUI%'
  AND ROWNUM <= 5;
```

### Últimos movimentos Stone

```sql
SELECT
    nr_sequencia,
    dt_transacao,
    vl_transacao,
    nr_seq_bandeira,
    ds_observacao,
    dt_atualizacao
FROM movto_cartao_cr
WHERE ds_observacao LIKE '%ID stone -%'
ORDER BY dt_atualizacao DESC
FETCH FIRST 50 ROWS ONLY;
```

### Contar movimentos Stone (aproximado)

```sql
SELECT COUNT(*)
FROM movto_cartao_cr
WHERE ds_observacao LIKE '%ID stone -%';
```

### Conferir duplicata (não deveria retornar > 1 por id)

```sql
SELECT
    REGEXP_SUBSTR(ds_observacao, 'ID stone - ([0-9A-Za-z]+)', 1, 1, NULL, 1) AS id_stone,
    COUNT(*) AS qtd
FROM movto_cartao_cr
WHERE ds_observacao LIKE '%ID stone -%'
GROUP BY REGEXP_SUBSTR(ds_observacao, 'ID stone - ([0-9A-Za-z]+)', 1, 1, NULL, 1)
HAVING COUNT(*) > 1;
```

### Caixas (Tasy)

`cd_caixa` do staging = `nr_sequencia` (ou equivalente) do caixa no Tasy.  
Troque `48` / datas pelos valores do seu teste.

```sql
-- Cadastro do caixa (ajuste nome da tabela/colunas se o Tasy do cliente diferir)
SELECT nr_sequencia, ds_caixa, ie_situacao
FROM caixa
WHERE nr_sequencia IN (11, 12, 15, 43, 48)
ORDER BY nr_sequencia;

-- Um caixa
SELECT nr_sequencia, ds_caixa, ie_situacao
FROM caixa
WHERE nr_sequencia = 48;

-- Saldo do dia (abertura do caixa na data)
SELECT nr_sequencia, nr_seq_caixa, dt_saldo, nm_usuario
FROM caixa_saldo_diario
WHERE nr_seq_caixa = 48
  AND dt_saldo = TO_DATE('2026-06-17', 'YYYY-MM-DD');

-- Saldos recentes de um caixa
SELECT nr_sequencia, nr_seq_caixa, dt_saldo, nm_usuario
FROM caixa_saldo_diario
WHERE nr_seq_caixa = 48
ORDER BY dt_saldo DESC
FETCH FIRST 20 ROWS ONLY;

-- Recebimentos do saldo do dia
SELECT
    cr.nr_sequencia,
    cr.nr_seq_saldo_caixa,
    cr.vl_especie,
    cr.nr_seq_trans_financ,
    cr.dt_recebimento,
    cr.nm_usuario
FROM caixa_receb cr
JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
WHERE csd.nr_seq_caixa = 48
  AND csd.dt_saldo = TO_DATE('2026-06-17', 'YYYY-MM-DD')
ORDER BY cr.nr_sequencia DESC;

-- Movimentos Stone ligados ao recebimento do caixa (via obs)
SELECT
    m.nr_sequencia,
    m.nr_seq_caixa_rec,
    m.dt_transacao,
    m.vl_transacao,
    m.ds_observacao
FROM movto_cartao_cr m
WHERE m.ds_observacao LIKE '%ID stone -%'
  AND m.nr_seq_caixa_rec IN (
      SELECT cr.nr_sequencia
      FROM caixa_receb cr
      JOIN caixa_saldo_diario csd ON csd.nr_sequencia = cr.nr_seq_saldo_caixa
      WHERE csd.nr_seq_caixa = 48
        AND csd.dt_saldo = TO_DATE('2026-06-17', 'YYYY-MM-DD')
  )
ORDER BY m.nr_sequencia DESC
FETCH FIRST 50 ROWS ONLY;
```

---

## Cruzar Postgres × Oracle

1. Pegue um `id_stone` com `cd_status = 5` no Postgres.  
2. Rode o `LIKE '%ID stone - ...%'` no Oracle → deve achar **1** linha.  
3. Pegue um com `cd_status = 7` → em geral **não** existe no Oracle (falhou antes do insert).  
4. Reextraia a mesma data: os status 5 devem logar `Já integrado (idempotente)`.

---

## Filas (RabbitMQ)

UI: http://localhost:15673 (`stone` / `stone`)

| Fila | Uso |
|------|-----|
| `stone.cartao.transactions` | Principal |
| `stone.cartao.transactions.retry` | Retry com delay |
| `stone.cartao.transactions.dlq` | Erros definitivos |

Purge só se quiser limpar teste antigo antes de reextrair.

---

## Painel web (recomendado em homolog/prod)

Lê direto o Postgres staging (`registro_maquininha` + caixas):

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao.painel
```

- UI: http://localhost:8001/painel  
- JSON: http://localhost:8001/api/registros  

Filtros na tela: data de/até, caixa, status, tipo (crédito/débito/PIX), id_stone, serial, autorização, bandeira, valor min/máx, texto da obs/erro.

Rode **junto** com o consumer (`poetry run python -m tasy_insercao`) — são processos separados.

---

## Checklist rápido de debug

1. Painel `/painel` ou `GROUP BY cd_status` no Postgres  
2. Ver `ds_obs_processo` dos status 6/7  
3. Conferir maquininha `ie_status = 'A'`  
4. Conferir mapeamento bandeira  
5. No Oracle: `LIKE '%ID stone -%'` para um id OK  
6. Logs do consumer: `Inserido` / `Já integrado` / `Falha` / `DLQ`

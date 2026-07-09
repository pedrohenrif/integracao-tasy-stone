# Contexto do Projeto: Integração Stone -> Tasy

## 1. Visão Geral
Automatizar a conciliação financeira: consumir transações da **Stone** e inserir no **Tasy**.

O legado (`GA111-IntegrarDadosMaquininhaStoneTasy`) usava scraping; a nova arquitetura usa API/Webhook Stone + filas.

## 2. Serviços (dois repositórios)

| Serviço | Pasta | Papel |
|---------|-------|-------|
| **stone-extracao** | `/stone-extracao` | Producer FastAPI: busca conciliação Cartão, parseia, publica na fila |
| **tasy-insercao** | `/tasy-insercao` | Consumer: regras de negócio + insert Oracle Tasy + staging Postgres |

Mensageria compartilhada: RabbitMQ (`docker-compose.yml` na raiz).

```
Stone API  →  stone-extracao  →  RabbitMQ  →  tasy-insercao  →  Postgres + Oracle Tasy
```

## 3. Arquitetura DDD
Cada serviço segue camadas: `domain` → `application` → `infrastructure` → `interfaces`.
O contrato da fila (`EventoFilaCartao`) é o ponto de integração entre os bounded contexts.

## 4. Fluxos

### Cartão (implementado)
- Batch: `POST /cartao/conciliation?date=YYYYMMDD` em **stone-extracao**
- Endpoint Stone: `https://conciliation.stone.com.br/v2/merchant/{merchant_id}/conciliation-file/{data}`

### PIX (fase 2)
- Webhook / extrato PIX — ainda não implementado

## 5. Retry e anti-duplicidade (tasy-insercao)
- Não descarta a mensagem em falha transitória: reenvia via fila **retry** com delay
- Após esgotar tentativas: vai para **DLQ** (payload preservado)
- Idempotência por `id_stone` (status PG + observação no `movto_cartao_cr`)

## 6. Regras de negócio (GA111)
Sequência: **Caixa → Dia → Transação** (cartão / parcelado). Fonte: `/GA111-IntegrarDadosMaquininhaStoneTasy`.

## 7. Workspace

| Pasta | Status |
|-------|--------|
| `/stone-extracao` | **Ativo** — extração |
| `/tasy-insercao` | **Ativo** — inserção |
| `/GA111-IntegrarDadosMaquininhaStoneTasy` | Legado (referência SQL/regras) |
| `/integracao-transacoes-tasy` | **Depreciado** (scaffold monolítico anterior) |
| `/api-pagar-me` | Obsoleto — ignorar |

## 8. Homologação (quando chegar a chave Stone)
1. Em `stone-extracao/.env`: `STONE_API_TOKEN=...` e `STONE_USE_SAMPLE=false`
2. Em `tasy-insercao/.env`: credenciais Postgres + Oracle de homolog
3. `docker compose up -d`
4. Subir os dois serviços e disparar `POST /cartao/conciliation`

## 9. Docs úteis
- API Conciliação Stone: https://conciliacao.stone.com.br/reference/o-que-e

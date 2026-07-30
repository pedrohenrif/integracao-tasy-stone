# Contexto do Projeto: Integração Stone -> Tasy

## 1. Visão Geral
Automatizar a conciliação financeira: consumir transações da **Stone** e inserir no **Tasy**.

O legado (`GA111-IntegrarDadosMaquininhaStoneTasy`) usava scraping; a nova arquitetura usa API/Webhook Stone + filas.

## 2. Serviços (dois repositórios)

| Serviço | Pasta | Papel |
|---------|-------|-------|
| **stone-extracao** | `/stone-extracao` | Producer FastAPI: Cartão (batch) + PIX (request/webhook) → filas |
| **tasy-insercao** | `/tasy-insercao` | Consumer: regras de negócio + insert Oracle + staging Postgres |

Mensageria compartilhada: RabbitMQ (`docker-compose.yml` na raiz).

```
Cartão: Stone API  → stone-extracao → stone.cartao.transactions → tasy-insercao → Tasy
PIX:    Stone API (request) → webhook público → stone.pix.transactions → tasy-insercao → Tasy
```

## 3. Arquitetura DDD
Cada serviço: `domain` → `application` → `infrastructure` → `interfaces`.  
Cartão e PIX são bounded contexts separados (filas e contratos distintos).

## 4. Fluxos

### Cartão
- `POST /cartao/conciliation?date=YYYYMMDD`
- Endpoint: `https://conciliation.stone.com.br/v2/merchant/{StoneCode}/conciliation-file/{data}`
- StoneCode exemplo: `116852622`

### PIX
1. Cadastrar webhook HTTPS: `POST /pix/webhook/register` → Stone `POST /v2/webhook`
2. Solicitar extrato: `POST /pix/conciliation/request?date=YYYY-MM-DD`
3. Stone notifica: `POST /pix/webhook` com `{"type":"pix","downloadUrl"|"url":"..."}`
4. Serviço baixa o CSV, parseia e publica em `stone.pix.transactions`
- Endpoint request: `POST https://conciliation.stone.com.br/v2/merchant/{CNPJ}/conciliation-file/pix/{data}`
- CNPJ exemplo: `76610690000162`
- Formato do extrato: CSV (valores em centavos)
- Pedido só após 03:00 do dia seguinte (regra Stone)

## 5. Retry e anti-duplicidade (tasy-insercao)
- Falha transitória → fila retry com delay
- Esgotou tentativas → DLQ (payload preservado)
- Idempotência por `id_stone`

## 6. Regras de negócio (GA111)
Sequência: **Caixa → Dia → Transação**.  
PIX no Tasy segue regra de débito.

## 7. Workspace

| Pasta | Status |
|-------|--------|
| `/stone-extracao` | **Ativo** |
| `/tasy-insercao` | **Ativo** |
| `/GA111-IntegrarDadosMaquininhaStoneTasy` | Legado (referência) |
| `/integracao-transacoes-tasy` | Depreciado (pode apagar) |
| `/api-pagar-me` | Obsoleto |

## 8. Homologação
1. `stone-extracao/.env`: `STONE_API_TOKEN`, `STONE_USE_SAMPLE=false`, `STONE_PIX_MERCHANT_ID`
2. `tasy-insercao/.env`: Postgres + Oracle homolog
3. Expor `/pix/webhook` publicamente (HTTPS) e cadastrar com `POST /pix/webhook/register`
4. `docker compose up -d` + subir os dois serviços

Passo a passo de testes locais: **[TESTES_LOCAIS.md](./TESTES_LOCAIS.md)**

## 9. Docs
- https://conciliacao.stone.com.br/reference/o-que-e

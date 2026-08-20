# stone-extracao

Serviço **Producer** da integração Stone → Tasy.

Extrai transações Stone (**Cartão** e **PIX**), valida e publica em filas RabbitMQ separadas.  
**Não** grava no Oracle/Tasy.

## Fluxos

### Cartão (batch)
```
POST /cartao/conciliation?date=YYYYMMDD   → data manual
POST /cartao/conciliation/d-1             → sempre ontem (D-1)
Cron diário (CARTAO_CRON_ENABLED=true)    → mesmo fluxo D-1
  → API Stone conciliation-file
  → fila stone.cartao.transactions
```

Rotina de produção: **sempre retroativo (D-1)** no fuso `America/Sao_Paulo`.  
Horário padrão do cron: **06:00**. Manual/backfill continua com `?date=YYYYMMDD`.

### PIX (request + webhook)
```
0) POST /pix/webhook/register  {"url":"https://seu-host/pix/webhook"}
     → Stone valida com {"type":"validation_notification"} (responder 2xx ≤3s)
1) POST /pix/conciliation/request?date=YYYY-MM-DD
     → solicita extrato na Stone (POST assíncrono)
2) POST /pix/webhook  (HTTPS público)
     → Stone envia {"type":"pix","downloadUrl"|"url":"..."}
     → baixamos o CSV, parseamos e publicamos
     → fila stone.pix.transactions
```

Dev/homolog sem webhook:

```http
POST /pix/conciliation/dev                      → sample, só terminais do seed
POST /pix/conciliation/dev?limit=5&terminal=PB09231S72079
```

Com `STONE_USE_SAMPLE=true`, o `POST /pix/conciliation/request` também publica o CSV local.

## DDD

```
domain/cartao/   domain/pix/
application/use_cases/
infrastructure/  (Stone API, parsers XML/CSV, RabbitMQ)
interfaces/api/
```

## Setup

```bash
cd stone-extracao
cp .env.example .env
# STONE_API_TOKEN=chave_do_portal_stone (sk_...)
# STONE_PIX_MERCHANT_ID=76610690000162
poetry install
```

Auth da API (Cliente Stone / lojista):
- `Authorization: Basic base64("{STONE_API_TOKEN}:")`
- `x-user-type: client`
- resposta pode vir em gzip (já tratado no client)

```bash
docker compose up -d   # na raiz Maq_Stone
poetry run uvicorn stone_extracao.interfaces.api.main:app --reload --port 8000
```

## Endpoints

| Método | Rota | Uso |
|--------|------|-----|
| GET | `/painel` | Painel HTML (última extração cartão) |
| GET | `/painel/api/cartao` | JSON com todas as txs da última extração |
| GET | `/health` | status + filas |
| POST | `/cartao/conciliation?date=20260708` | extrato cartão (data manual) |
| POST | `/cartao/conciliation/d-1` | extrato cartão do **dia anterior** |
| POST | `/pix/conciliation/request?date=2026-07-08` | solicita PIX |
| POST | `/pix/webhook` | notificação PIX (público HTTPS) |
| POST | `/pix/webhook/register` | cadastra URL na Stone (`/v2/webhook`) |
| PUT | `/pix/webhook/register` | atualiza URL na Stone |
| POST | `/pix/conciliation/dev` | sample PIX local |

## Observações PIX

- Merchant PIX (`STONE_PIX_MERCHANT_ID`) pode ser diferente do StoneCode do cartão.
- O arquivo PIX do sample é **CSV** (mesmo com extensão `.xml`).
- Valores PIX vêm em **centavos**; o parser converte para reais.
- Webhook oficial: JSON com `downloadUrl` ou `url` (não o CSV no body). CSV cru ainda é aceito para homolog.
- Cadastro: `POST https://conciliation.stone.com.br/v2/webhook` com `{"url":"https://..."}` (HTTPS obrigatório).
- Pedido de extrato: só após **03:00** do dia seguinte à data de referência (regra Stone).
- Responder `validation_notification` e notificação PIX com HTTP 200 rápido (≤3s / ≤5s).

## Rotina D-1 (prod-like)

No `.env`:

```env
CARTAO_CRON_ENABLED=true
CARTAO_CRON_HOUR=4          # 0-23 — Stone cartão só após 04:00 BRT
CARTAO_CRON_MINUTE=0
CARTAO_CRON_RETRY_HOUR=5
CARTAO_CRON_TZ=America/Sao_Paulo

PIX_CRON_ENABLED=true
PIX_CRON_HOUR=4
PIX_CRON_MINUTE=5
# STONE_PIX_MERCHANT_ID = CNPJ 14 dígitos (não use o StoneCode do cartão)
```

Subir **sem** `--reload` (evita job duplicado):

```powershell
poetry run uvicorn stone_extracao.interfaces.api.main:app --host 0.0.0.0 --port 8000
```

- Cron: todo dia no horário configurado → busca **ontem** → publica todas as txs  
- Manual agora: `POST /cartao/conciliation/d-1`  
- Backfill: `POST /cartao/conciliation?date=YYYYMMDD`  
- Status do cron: `GET /health` → campo `cartao_cron`

## Testes locais (extração + painel)

Guia completo na raiz: [TESTES_LOCAIS.md](../TESTES_LOCAIS.md)

```powershell
# RabbitMQ (raiz do repo)
docker compose up -d

# API
poetry run uvicorn stone_extracao.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000

# Extrair D-1 (ontem)
curl -X POST "http://localhost:8000/cartao/conciliation/d-1"

# Extrair data específica
curl -X POST "http://localhost:8000/cartao/conciliation?date=20260617"

# Painel
# http://localhost:8000/painel
```

## Testes unitários

```powershell
poetry run pytest -q
```

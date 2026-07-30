# Testes locais — Stone → Tasy

Guia prático para validar o fluxo em duas etapas no ambiente local.

---

## Pré-requisitos

- Docker Desktop rodando
- Python 3.10+ e Poetry
- Credenciais Stone no `stone-extracao/.env` (`STONE_API_TOKEN`, `STONE_MERCHANT_ID`)
- Para a 2ª parte: Postgres staging + Oracle Tasy (homolog) no `tasy-insercao/.env`

---

## Parte 1 — Extração de cartão (já validada)

Objetivo: buscar extrato na Stone, publicar na fila e visualizar no painel.

### 1.1 Subir RabbitMQ

Na raiz `Maq_Stone`:

```powershell
cd "c:\Users\pedro\OneDrive\Área de Trabalho\GHR Tech\Cliente\Cotolengo\Maq_Stone"
docker compose up -d
docker compose ps
```

| Serviço | URL |
|---------|-----|
| AMQP | `localhost:5673` |
| Management UI | http://localhost:15673 (`stone` / `stone`) |

### 1.2 Subir stone-extracao

```powershell
cd "c:\Users\pedro\OneDrive\Área de Trabalho\GHR Tech\Cliente\Cotolengo\Maq_Stone\stone-extracao"
poetry install
poetry run uvicorn stone_extracao.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000
```

| Recurso | URL |
|---------|-----|
| Health | http://localhost:8000/health |
| Swagger | http://localhost:8000/docs |
| Painel | http://localhost:8000/painel |
| JSON | http://localhost:8000/painel/api/cartao |

### 1.3 Extrair cartão

Rotina de produção (sempre **ontem** / D-1):

```powershell
curl -X POST "http://localhost:8000/cartao/conciliation/d-1"
```

Data específica (`YYYYMMDD`) para backfill:

```powershell
curl -X POST "http://localhost:8000/cartao/conciliation?date=20260617"
```

Resposta esperada: `200`, `source: stone_api`, `parsed_count` / `published_count` > 0.

Cron diário (homolog/prod): no `.env` `CARTAO_CRON_ENABLED=true` e subir uvicorn **sem** `--reload`. Ver `GET /health` → `cartao_cron`.

### 1.4 Visualizar

1. Abrir http://localhost:8000/painel (rode a extração de novo se reiniciou o uvicorn — painel é em memória)
2. Opcional: fila no RabbitMQ UI → `stone.cartao.transactions` → Get messages

### Auth Stone (Cliente / lojista)

Já implementada no código:

- `Authorization: Basic base64("{STONE_API_TOKEN}:")`
- `x-user-type: client`
- follow redirect `307` + gzip

Confirme no `.env` o **StoneCode correto** do estabelecimento (`STONE_MERCHANT_ID`).

---

## Parte 2 — Inserção Tasy (homolog)

Objetivo: consumir a fila e gravar no Postgres staging + Oracle Tasy de homologação.

### 2.1 Configurar `.env` do tasy-insercao

```powershell
cd "c:\Users\pedro\OneDrive\Área de Trabalho\GHR Tech\Cliente\Cotolengo\Maq_Stone\tasy-insercao"
copy .env.example .env
```

Preencha (homolog):

```env
RABBITMQ_URL=amqp://stone:stone@localhost:5673/

POSTGRES_USER=...
POSTGRES_PASS=...
POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DB=...

ORACLE_USER=...
ORACLE_PASS=...
ORACLE_DSN=...
```

### 2.2 Subir schema + seed do Postgres (staging)

Com o `.env` do `tasy-insercao` preenchido:

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao.db up
poetry run python -m tasy_insercao.db status
```

Isso cria (estilo Prisma):

| Tabela | Uso |
|--------|-----|
| `caixas_tasy` | caixas do hospital |
| `maquininha_stone` | serial → `cd_caixa` + `cd_transacao_financeira` |
| `mapeamento_transacoes_tasy` | tipo + bandeira → `cd_cartao_bandeira_tasy` |
| `registro_maquininha` | staging / status por `id_stone` |

**Ainda falta preencher na homolog (não temos os IDs do Tasy no código):**

1. `UPDATE mapeamento_transacoes_tasy SET cd_cartao_bandeira_tasy = ...` com os `nr_sequencia` reais das bandeiras no Oracle  
2. Cadastrar maquininhas (template: `db/seed_maquininhas.example.sql`)

Detalhes: [tasy-insercao/db/README.md](./tasy-insercao/db/README.md)

### 2.3 Subir o consumer

Com RabbitMQ + (opcional) já ter mensagens na fila:

```powershell
cd "c:\Users\pedro\OneDrive\Área de Trabalho\GHR Tech\Cliente\Cotolengo\Maq_Stone\tasy-insercao"
poetry install
poetry run python -m tasy_insercao
```

Logs esperados:

- `Consumer iniciado | cartao=... | pix=...`
- `Recebido fila | cartao | id_stone=...`
- `Inserido | cartao | ...` **ou** `Falha | ...` / `Retry agendado`

### 2.4 Fluxo completo sugerido (homolog)

1. RabbitMQ up (`docker compose up -d`)
2. `stone-extracao` up
3. Extrair data pequena/conhecida: `POST /cartao/conciliation?date=YYYYMMDD`
4. Conferir no painel
5. Subir `tasy-insercao`
6. Acompanhar logs do consumer
7. Validar no Postgres: `registro_maquininha` (`cd_status` 5 = ok, 6/7 = erro)
8. Validar no Oracle Tasy: `movto_cartao_cr` com observação `ID stone - {id}`

### 2.5 Status no Postgres

| `cd_status` | Significado |
|-------------|-------------|
| 1 | Pendente |
| 2 | Processando |
| 5 | Integrado |
| 6 | Erro com retry |
| 7 | Erro definitivo (DLQ) |

SELECTs de debug (Postgres + Oracle) e idempotência: **[tasy-insercao/DEBUG.md](./tasy-insercao/DEBUG.md)**

Painel web com filtros (datas, caixa, status, tipo, id_stone, valores…):

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao.painel
# http://localhost:8001/painel
```

### 2.6 Se a fila estiver “suja” de testes antigos

No RabbitMQ UI (http://localhost:15673):

- Queues → `stone.cartao.transactions` → **Purge Messages**
- Queues → `stone.pix.transactions` (+ `.retry` / `.dlq` se precisar) → **Purge**

Depois extraia de novo só a data que quiser validar.

---

## Parte 3 — PIX (homolog com sample)

Pré-requisitos: RabbitMQ + `stone-extracao` + `tasy-insercao` (consumer) já no ar, VPN Oracle se for inserir no Tasy.

PIX no Tasy = **débito** (`ie_tipo_cartao=D`), vencimento **no dia**, bandeira Tasy **21** (tipo Pix no seed).  
No staging fica `cd_tipo_transacao = pix` (filtro no painel debug).

### 3.1 Teste rápido com sample (recomendado)

```powershell
# 1º teste: só 5 txs de um terminal já no seed
curl -X POST "http://localhost:8000/pix/conciliation/dev?limit=5&terminal=PB09231S72079"

# Sample completo só com terminais cadastrados (default only_seeded=true)
curl -X POST "http://localhost:8000/pix/conciliation/dev"
```

Esperado: `published_count` > 0, fila `stone.pix.transactions`.

Logs consumer:

- `Recebido fila | pix | id_stone=...`
- `Inserido | pix | ...` **ou** `Já integrado (idempotente)`

Validar:

```powershell
# Painel staging — filtrar Tipo = PIX
# http://localhost:8001/painel
```

```sql
SELECT cd_status, COUNT(*) FROM registro_maquininha
WHERE cd_tipo_transacao = 'pix' GROUP BY 1;
```

### 3.2 Fluxo oficial Stone (webhook HTTPS)

Pré-requisitos: `STONE_USE_SAMPLE=false`, `STONE_API_TOKEN` preenchido, URL **HTTPS pública** apontando para `POST /pix/webhook` (túnel/ngrok/homolog).

```powershell
# 0) Cadastrar (ou atualizar) o webhook na Stone
#    A Stone chama /pix/webhook com {"type":"validation_notification"} — deve responder 2xx em ≤3s
curl -X POST "http://localhost:8000/pix/webhook/register" `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"https://SEU-HOST-PUBLICO/pix/webhook\"}"

# Se já existir (409), atualize:
curl -X PUT "http://localhost:8000/pix/webhook/register" `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"https://SEU-HOST-PUBLICO/pix/webhook\"}"

# 1) Solicita extrato (date = YYYY-MM-DD) — só após 03:00 do dia seguinte
curl -X POST "http://localhost:8000/pix/conciliation/request?date=2026-07-08"

# 2) Stone posta JSON em POST /pix/webhook, por exemplo:
#    {"type":"pix","downloadUrl":"<url-assinada>"}  ou  {"type":"pix","url":"..."}
#    O serviço baixa o CSV em background e publica na fila.
```

`STONE_PIX_MERCHANT_ID` = CNPJ (pode diferir do StoneCode do cartão).

Simular notificação local (sem Stone):

```powershell
curl -X POST "http://localhost:8000/pix/webhook" `
  -H "Content-Type: application/json" `
  -d "{\"type\":\"validation_notification\"}"
```

### 3.3 Modo sample no request

Com `STONE_USE_SAMPLE=true` no `.env` da extração, o `POST /pix/conciliation/request` já lê o CSV local e **publica** na fila (paridade com cartão).

---

## Ordem dos terminais

| Terminal | Comando |
|----------|---------|
| 1 | `docker compose up -d` (raiz) |
| 2 | `poetry run uvicorn ...` em `stone-extracao` |
| 3 | `poetry run python -m tasy_insercao` em `tasy-insercao` |
| 4 (opc.) | `poetry run python -m tasy_insercao.painel` → :8001 |

---

## Checklist rápido

**Parte 1 — Cartão**

- [ ] Docker RabbitMQ up
- [ ] Token + StoneCode corretos no `.env` da extração
- [ ] `POST /cartao/conciliation` retorna 200
- [ ] Painel mostra as transações

**Parte 2 — Inserção**

- [ ] `.env` do `tasy-insercao` com Postgres + Oracle homolog
- [ ] Maquininhas mapeadas no staging
- [ ] Consumer sobe sem erro de conexão
- [ ] Mensagens saem da fila (`Ready` → 0)
- [ ] Status 5 no Postgres / movimento no Tasy

**Parte 3 — PIX**

- [ ] `POST /pix/conciliation/dev?limit=5&terminal=PB09231S72079` publica
- [ ] Consumer loga `Inserido | pix`
- [ ] Painel `:8001` com Tipo=PIX / status 5
- [ ] Oracle: `ds_observacao LIKE '%PIX%ID stone%'` (opcional)
- [ ] (oficial) URL HTTPS cadastrada via `/pix/webhook/register`
- [ ] (oficial) `validation_notification` responde 200
- [ ] (oficial) notificação com `downloadUrl`/`url` publica na fila

---

## Problemas comuns

| Sintoma | Ação |
|---------|------|
| `403 Forbidden` Stone | Auth/chave/StoneCode do estabelecimento |
| `307` sem follow | Já tratado no código (`follow_redirects`) |
| PIX webhook 422 / 0 txs | Esperar JSON com `downloadUrl`/`url` (não CSV no body no fluxo oficial) |
| Cadastro webhook 400 | URL precisa ser **HTTPS** pública |
| Cadastro webhook 409 | Já existe — use `PUT /pix/webhook/register` |
| Painel vazio | Rodar a extração de novo (memória) |
| Consumer: maquininha não cadastrada | Incluir serial em `maquininha_stone` |
| Consumer: mapeamento não encontrado | Ajustar `mapeamento_transacoes_tasy` |
| Oracle/PG connection error | Retry automático; conferir rede/VPN/DSN |

Documentação geral: [context.md](./context.md) · [stone-extracao/README.md](./stone-extracao/README.md) · [tasy-insercao/README.md](./tasy-insercao/README.md)

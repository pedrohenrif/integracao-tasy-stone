# tasy-insercao

Serviço **Consumer** da integração Stone → Tasy.

Consome filas **cartão** e **PIX** (separadas), aplica regras GA111 e grava no Oracle, com staging no Postgres e retry/DLQ.

## Filas

| Fluxo | Principal | Retry | DLQ |
|-------|-----------|-------|-----|
| Cartão | `stone.cartao.transactions` | `.retry` | `.dlq` |
| PIX | `stone.pix.transactions` | `.retry` | `.dlq` |

## Regras

- **Cartão:** crédito / débito / parcelado (GA111)
- **PIX:** staging `cd_tipo_transacao=pix`; Tasy = débito (`ie_tipo=D`, vencimento no dia, bandeira 21); `e2e_id` → `cd_autorizacao`
- Idempotência por `id_stone`
- Falha transitória → retry com delay; esgotou → DLQ (não descarta payload)

## Debug (SELECTs + status)

Ver **[DEBUG.md](./DEBUG.md)** — idempotência, `cd_status`, queries Postgres/Oracle.

### Portal de controle (React + API)

API (JWT + registros + filas):

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao.db schema   # inclui portal_usuario / login_log
poetry run python -m tasy_insercao.painel      # :8001
```

Front:

```powershell
cd portal-controle
npm install
npm run dev   # :5173
```

Login seed: `admin` / `admin123` (trocar em prod).  
Detalhes: [../portal-controle/README.md](../portal-controle/README.md)

## Setup (homolog)

```powershell
cd tasy-insercao
copy .env.example .env
# preencher POSTGRES_* e ORACLE_*
poetry install
```

### Subir schema do Postgres (tipo Prisma `db push`)

```powershell
poetry run python -m tasy_insercao.db up
poetry run python -m tasy_insercao.db status
```

Isso cria as tabelas e o seed de mapeamento (bandeiras/tipos).  
Depois é **obrigatório** preencher `cd_cartao_bandeira_tasy` com os IDs reais do Tasy e cadastrar as maquininhas — ver [db/README.md](./db/README.md).

```powershell
# exemplo de maquininhas (ajuste os códigos do hospital)
poetry run python -m tasy_insercao.db seed --file db/seed_maquininhas.example.sql

# consumer
poetry run python -m tasy_insercao
```

RabbitMQ: `docker compose up -d` na raiz · `amqp://stone:stone@localhost:5673/`

### Variáveis obrigatórias

| Grupo | Variáveis |
|-------|-----------|
| RabbitMQ | `RABBITMQ_URL`, filas (já no `.env.example`) |
| Postgres | `POSTGRES_USER`, `POSTGRES_PASS`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` |
| Oracle | `ORACLE_USER`, `ORACLE_PASS`, `ORACLE_DSN` |

### Staging (models em `infrastructure/persistence/models.py`)

- `caixas_tasy` / `maquininha_stone` — serial → caixa / transação financeira  
- `mapeamento_transacoes_tasy` — tipo + bandeira → bandeira Tasy  
- `registro_maquininha` — status por `id_stone`
## Status Postgres

| Código | Significado |
|--------|-------------|
| 1 | Pendente |
| 2 | Processando |
| 5 | Integrado |
| 6 | Erro com retry |
| 7 | Erro definitivo (DLQ) |

## Teste ponta a ponta

1. Extrair cartão no `stone-extracao` (`POST /cartao/conciliation`)
2. Subir este consumer
3. Ver logs `Inserido` / `Falha` / `Retry`
4. Conferir `registro_maquininha` e `movto_cartao_cr` no Tasy

Guia detalhado: [../TESTES_LOCAIS.md](../TESTES_LOCAIS.md)

## Testes unitários

```powershell
poetry run pytest -q
```

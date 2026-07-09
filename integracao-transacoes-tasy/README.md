# Integração Stone → Tasy

Captura de extrato **Cartão** da Stone (FastAPI Producer) → RabbitMQ → Consumer que integra no Tasy (Oracle) seguindo **Caixa → Dia → Transação → Documento**.

## Arquitetura (Cartão)

```
Stone Conciliation XML  →  FastAPI (Producer)  →  RabbitMQ  →  Consumer → Postgres staging + Oracle Tasy
```

- **Cartão:** `POST /cartao/conciliation` — implementado.
- **Consumer Tasy:** Caixa → Dia → Transação — implementado (portado do GA111).
- **PIX:** webhook — **fase 2** (não implementado).

## Pré-requisitos

- Python 3.10+
- Poetry
- Docker (RabbitMQ local)
- Acesso ao Postgres de staging e Oracle Tasy (`.env`)

## Setup

```bash
cd integracao-transacoes-tasy
cp .env.example .env
# preencha POSTGRES_* e ORACLE_*
poetry install
docker compose up -d
```

Management UI RabbitMQ: http://localhost:15673 (`stone` / `stone`).  
Portas **5673** / **15673** evitam conflito com outros Rabbit locais.

## Subir a API (Producer)

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
curl -X POST "http://localhost:8000/cartao/conciliation?date=20260708&use_sample=true"
```

Publica **1 mensagem por transação** em `stone.cartao.transactions`.

## Subir o Consumer

```bash
poetry run python -m app.consumer.worker
```

Fluxo por mensagem:

1. Valida payload Pydantic  
2. Idempotência: `registro_maquininha.cd_status=5` ou `movto_cartao_cr` com `ID stone - {id}`  
3. Resolve `maquininha_stone` (caixa + transação financeira)  
4. Staging no Postgres (`registro_maquininha`)  
5. Oracle: saldo diário → `caixa_receb` → `movto_cartao_cr` → `movto_trans_financ`  
6. Atualiza status PG: `5` ok / `6` erro  

Logs: `Recebido fila` → `Caixa` → `Dia` → `Transação` → `Inserido` / `Falha`.

## Testes

```bash
poetry run pytest -q
```

## Estrutura

```
app/
  api/           # FastAPI (cartão + health)
  consumer/      # worker RabbitMQ → TasyService
  core/          # config, logging, rabbit, oracle, postgres
  jobs/          # fetch conciliation
  parsers/       # XML Layout 2.2 cartão
  queries/       # SQL Oracle + Postgres
  schemas/       # Pydantic
  services/      # TasyService (regras de negócio)
  utils/         # money / brand map
```

## Próximas fases

1. Fluxo PIX (webhook + parser).
2. UNIQUE em `registro_maquininha.id_stone` no Postgres (se ainda não existir).
3. Otimizar lote: reutilizar um `caixa_receb` por máquina/dia em vez de um por mensagem.

# stone-extracao

Serviço **Producer** da integração Stone → Tasy.

Responsável por **extrair** o extrato de cartão da Stone, validar e **publicar** na fila RabbitMQ.  
**Não** grava no Oracle/Tasy.

## DDD (camadas)

```
src/stone_extracao/
  domain/cartao/          # modelos + ports (contrato da fila)
  application/use_cases/  # ExtrairConciliacaoCartao
  infrastructure/         # Stone API, parser XML, RabbitMQ, config
  interfaces/api/         # FastAPI
```

## Pré-requisitos

- Python 3.10+
- Poetry
- RabbitMQ (`docker compose up -d` na raiz do workspace)

## Setup

```bash
cd stone-extracao
cp .env.example .env
poetry install
```

### Quando receber a chave da Stone

No `.env`:

```env
STONE_API_TOKEN=sua_chave_aqui
STONE_USE_SAMPLE=false
STONE_MERCHANT_ID=116852622
```

Com isso, `POST /cartao/conciliation` chama a API real de conciliação.

Para dev sem token:

```env
STONE_USE_SAMPLE=true
```

## Subir

```bash
# na raiz Maq_Stone
docker compose up -d

cd stone-extracao
poetry run uvicorn stone_extracao.interfaces.api.main:app --reload --port 8000
```

- Health: `GET http://localhost:8000/health` (mostra se o token está configurado)
- Docs: http://localhost:8000/docs
- Extrair: `POST /cartao/conciliation?date=20260708`

## Fila publicada

- Exchange: `stone.direct`
- Queue: `stone.cartao.transactions`
- Payload: `EventoFilaCartao` (1 mensagem por transação)

## PIX

Fase 2 — não implementado neste serviço ainda.

## Testes

```bash
poetry run pytest -q
```

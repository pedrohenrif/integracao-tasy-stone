# Maq_Stone — Integração Stone → Tasy

## Serviços ativos

| Serviço | Descrição | Como subir |
|---------|-----------|------------|
| [stone-extracao](./stone-extracao) | Extração Stone (FastAPI Producer) | `poetry run uvicorn stone_extracao.interfaces.api.main:app --port 8000` |
| [tasy-insercao](./tasy-insercao) | Inserção Tasy (Consumer + retry/DLQ) | `poetry run python -m tasy_insercao` |

## Infra compartilhada

```bash
docker compose up -d   # RabbitMQ :5673 / UI :15673 (stone/stone)
```

## Fluxo

```
Stone API → stone-extracao → RabbitMQ → tasy-insercao → Postgres staging + Oracle Tasy
```

## Homologação (checklist)

1. Copiar `.env.example` → `.env` em cada serviço  
2. Colocar `STONE_API_TOKEN` em `stone-extracao` e `STONE_USE_SAMPLE=false`  
3. Preencher Postgres + Oracle em `tasy-insercao`  
4. Subir RabbitMQ + os dois processos  
5. `POST http://localhost:8000/cartao/conciliation?date=YYYYMMDD`

Documentação detalhada: [context.md](./context.md)

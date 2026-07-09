# tasy-insercao

Serviço **Consumer** da integração Stone → Tasy.

Consome a fila RabbitMQ, aplica regras de negócio (Caixa → Dia → Transação → Documento) e grava no **Oracle Tasy**, com staging/status no **Postgres**.

## DDD (camadas)

```
src/tasy_insercao/
  domain/integracao/       # modelos, status, policies (retryable), ports
  application/use_cases/   # IntegrarTransacaoCartao
  infrastructure/          # Oracle, Postgres, Rabbit (retry/DLQ), SQL
  interfaces/worker/       # consumer process
```

## Retry sem descartar a transação

| Situação | Ação |
|----------|------|
| Sucesso / já integrado | ack + status `5` |
| Erro transitório (rede, Oracle/PG down) | status `6` + **reenvio** para fila retry com TTL (30s→10min) |
| Após N tentativas ou erro de negócio | status `7` + mensagem vai para **DLQ** (payload preservado) |

Idempotência: antes de inserir, verifica `registro_maquininha.cd_status=5` e `movto_cartao_cr` com `ID stone - {id}`.

Filas:

- `stone.cartao.transactions` — principal
- `stone.cartao.transactions.retry` — espera (TTL) e volta à principal
- `stone.cartao.transactions.dlq` — falhas definitivas (não perde o dado)

## Setup

```bash
cd tasy-insercao
cp .env.example .env
# preencha POSTGRES_* e ORACLE_* (homolog)
poetry install
```

## Subir

```bash
# RabbitMQ na raiz
docker compose up -d

cd tasy-insercao
poetry run python -m tasy_insercao
```

## Status no Postgres (`registro_maquininha.cd_status`)

| Código | Significado |
|--------|-------------|
| 1 | Pendente |
| 2 | Processando |
| 5 | Integrado |
| 6 | Erro com retry |
| 7 | Erro definitivo (DLQ) |

## Testes

```bash
poetry run pytest -q
```

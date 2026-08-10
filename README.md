# Maq_Stone — Integração Stone → Tasy

## Serviços ativos

| Serviço | Descrição | Como subir |
|---------|-----------|------------|
| [stone-extracao](./stone-extracao) | Extração Stone — Cartão + PIX (FastAPI) | `poetry run uvicorn stone_extracao.interfaces.api.main:app --reload --port 8000` |
| [tasy-insercao](./tasy-insercao) | Inserção Tasy (Consumer cartão/PIX + retry/DLQ) | `poetry run python -m tasy_insercao` |
| [portal-controle](./portal-controle) | Portal React (login, integrações, erros, filas) | API `:8001` + `npm run dev` → :5173 |

## Infra compartilhada

```powershell
docker compose up -d   # RabbitMQ :5673 / UI :15673 (stone/stone)
```

## Fluxos

```
Cartão: cron/API D-1 → stone-extracao → stone.cartao.transactions → tasy-insercao → Tasy
PIX:    request → webhook /pix/webhook → stone.pix.transactions → tasy-insercao → Tasy
```

Cartão em prod: sempre **retroativo (dia anterior)**. Endpoint `POST /cartao/conciliation/d-1` ou cron (`CARTAO_CRON_*`).  
PIX em prod: `POST /pix/conciliation/d-1` ou cron (`PIX_CRON_*`) — solicita extrato; Stone entrega no webhook.

## Deploy VM Windows (Cotolengo)

Ver **[DEPLOY_VM_WINDOWS.md](./DEPLOY_VM_WINDOWS.md)** (clone, Postgres, RabbitMQ, portal, **como reiniciar serviços**).

- Portal interno: `http://stone.financeiro:5173`
- Webhook PIX: `https://stone.pequenocotolengo.org.br/pix/webhook`

## Testes locais (passo a passo)

Ver guia completo: **[TESTES_LOCAIS.md](./TESTES_LOCAIS.md)**

Resumo:

1. **Parte 1 — Extração:** Docker + `stone-extracao` → `POST /cartao/conciliation` → painel `/painel`
2. **Parte 2 — Homolog:** preencher `.env` do `tasy-insercao` (Postgres + Oracle) → subir consumer → validar status/Tasy

## Homologação (checklist)

1. Copiar `.env.example` → `.env` em cada serviço  
2. `STONE_API_TOKEN` + `STONE_MERCHANT_ID` corretos em `stone-extracao`  
3. Postgres + Oracle homolog em `tasy-insercao`  
4. Cadastro de maquininhas / mapeamento no staging  
5. Subir RabbitMQ + os dois processos  

Documentação: [context.md](./context.md) · Debug insert: [tasy-insercao/DEBUG.md](./tasy-insercao/DEBUG.md)

# Portal de controle — Stone → Tasy

Front **React (Vite)** + API **FastAPI** do `tasy-insercao` (porta 8001).

## O que tem

- Login JWT + usuário admin seed
- Logs de acesso (admin)
- Dashboard (totais + filas)
- Integrações com filtros (Postgres staging)
- Erros / DLQ
- Filas RabbitMQ (Management API)

## Subir

### 1) Schema portal + API

```powershell
cd tasy-insercao
# no .env: PORTAL_* e POSTGRES_* (ver .env.example)
poetry run python -m tasy_insercao.db schema
poetry run python -m tasy_insercao.painel
```

API: http://localhost:8001/docs  
Login padrão (seed): `admin` / `admin123` — **troque em prod**.

### 2) Front React

```powershell
cd portal-controle
npm install
npm run dev
```

UI: http://localhost:5173  

O Vite faz proxy de `/api` → `http://localhost:8001`.

## Variáveis

**tasy-insercao/.env**

```env
PORTAL_JWT_SECRET=troque-em-producao
PORTAL_ADMIN_USER=admin
PORTAL_ADMIN_PASS=admin123
PORTAL_CORS_ORIGINS=http://localhost:5173
RABBITMQ_MGMT_URL=http://localhost:15673
RABBITMQ_MGMT_USER=stone
RABBITMQ_MGMT_PASS=stone
```

**portal-controle** — opcional `VITE_API_URL` se a API não estiver no proxy.

## Endpoints usados

| Método | Rota | Auth |
|--------|------|------|
| POST | `/api/auth/login` | não |
| GET | `/api/auth/me` | sim |
| GET | `/api/auth/login-logs` | admin |
| GET | `/api/registros` | sim |
| GET | `/api/caixas` | sim |
| GET | `/api/filas` | sim |

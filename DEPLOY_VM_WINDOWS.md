# Deploy VM Windows (Cotolengo)

Guia rápido para clonar e subir na VM do cliente (`10.1.1.190` / subdomínio interno).

## Pré-requisitos na VM

- Git
- Python 3.10+
- [Poetry](https://python-poetry.org/)
- Node.js 20+ (só para build do portal)
- Docker Desktop (RabbitMQ)
- PostgreSQL (local na VM)
- Acesso Oracle homolog (VPN/rede, se necessário)
- Firewall liberando portas internas: `80/443` (portal), opcional `8000/8001`

> IP `10.x` é interno: o **portal** funciona na rede do hospital.  
> Webhook PIX da Stone (internet) só funciona com IP público/NAT **ou** Cloudflare Tunnel.

## 1) Clonar

```powershell
cd C:\apps   # ou pasta combinada com o TI
git clone https://github.com/pedrohenrif/integracao-tasy-stone.git Maq_Stone
cd Maq_Stone
```

## 2) RabbitMQ

```powershell
docker compose up -d
docker compose ps
```

- AMQP: `localhost:5673`
- UI: http://localhost:15673 (`stone` / `stone`)

## 3) Postgres + schema

1. Crie um banco (ex.: `maquina_stone`) e usuário.
2. Copie envs:

```powershell
copy stone-extracao\.env.example stone-extracao\.env
copy tasy-insercao\.env.example tasy-insercao\.env
copy portal-controle\.env.example portal-controle\.env   # se existir
```

3. Preencha `tasy-insercao\.env` (Postgres, Oracle, Rabbit, `STONE_EXTRACAO_BASE_URL=http://127.0.0.1:8000`, `PORTAL_CORS_ORIGINS` com a URL do portal na rede).
4. Preencha `stone-extracao\.env` (`STONE_API_TOKEN`, merchants, `STONE_USE_SAMPLE=false`).

```powershell
cd tasy-insercao
poetry install
poetry run python -m tasy_insercao.db schema
poetry run python -m tasy_insercao.db seed   # se disponível / necessário
```

## 4) Serviços (3 terminais ou NSSM/Task Scheduler)

**stone-extracao (producer + webhook + cron)**

```powershell
cd stone-extracao
poetry install
poetry run uvicorn stone_extracao.interfaces.api.main:app --host 0.0.0.0 --port 8000
```

**tasy-insercao (consumer)**

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao
```

**portal API**

```powershell
cd tasy-insercao
poetry run python -m tasy_insercao.painel
# escuta :8001
```

## 5) Portal React (acesso na rede)

```powershell
cd portal-controle
npm install
npm run build
```

Sirva a pasta `dist` com IIS/Nginx/Caddy **ou**:

```powershell
npm run preview -- --host 0.0.0.0 --port 5173
```

Proxy sugerido no subdomínio:
- `/` → portal estático (ou :5173)
- `/api` e `/health` → `http://127.0.0.1:8001`
- `/pix` e `/cartao` e `/scheduler` → `http://127.0.0.1:8000` (webhook PIX)

Ajuste `VITE_API_URL` / CORS se o front chamar a API por URL absoluta.

## 6) Checklist pós-subida

- [ ] http://VM:8000/health
- [ ] http://VM:8001/health
- [ ] Login portal (`admin` / senha do `.env`)
- [ ] Scheduler (admin) — ativar quando for usar cron D-1
- [ ] `POST /cartao/conciliation/d-1` smoke
- [ ] PIX: só após HTTPS público + `POST /pix/webhook/register`

## Credenciais

Nunca commitar `.env`. Rotacionar `PORTAL_ADMIN_PASS` e `PORTAL_JWT_SECRET` na VM.

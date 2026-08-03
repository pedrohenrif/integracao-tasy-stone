# Deploy VM Windows (Cotolengo)

Guia para clonar e subir na VM (`10.1.1.190` / `https://stone.pequenocotolengo.org.br`).

## Pré-requisitos na VM

- Git, Python 3.10+, [Poetry](https://python-poetry.org/), Node.js 20+
- PostgreSQL local
- **RabbitMQ nativo** (Docker Desktop costuma falhar sem nested virtualization)
- [NSSM](https://nssm.cc/download) — serviços Windows sem terminal
- Firewall: `80/443` (portal), opcional `8000/8001/5173`

> IP `10.x` é interno: portal na rede do hospital.  
> Webhook PIX da Stone (internet) só com HTTPS público (NAT/proxy/Tunnel).

## 1) Clonar

```powershell
cd C:\GHR_Tech
git clone https://github.com/pedrohenrif/integracao-tasy-stone.git integracao-tasy-stone
cd integracao-tasy-stone
```

## 2) RabbitMQ (nativo — recomendado na VM)

1. Instalar **Erlang OTP 27.x** (não usar 28/29 com RabbitMQ 4.3).
2. Instalar RabbitMQ Server Windows.
3. Serviço automático + usuário:

```powershell
cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-*\sbin"
.\rabbitmq-plugins.bat enable rabbitmq_management
.\rabbitmq-service.bat install
.\rabbitmq-service.bat start
Set-Service RabbitMQ -StartupType Automatic

# Se rabbitmqctl falhar por cookie: copiar
#   %WINDIR%\System32\config\systemprofile\.erlang.cookie
# para %USERPROFILE%\.erlang.cookie e %APPDATA%\RabbitMQ\.erlang.cookie

.\rabbitmqctl.bat add_user stone stone
.\rabbitmqctl.bat set_user_tags stone administrator
.\rabbitmqctl.bat set_permissions -p / stone ".*" ".*" ".*"
```

- AMQP: `localhost:5672`
- UI: http://localhost:15672 (`stone` / `stone`)

Nos `.env` use portas **5672 / 15672** (não 5673 do Docker).

## 3) Postgres + .env + seed

```powershell
copy stone-extracao\.env.example stone-extracao\.env
copy tasy-insercao\.env.example tasy-insercao\.env
```

Preencher Postgres, Oracle, `STONE_API_TOKEN`, CORS com o subdomínio:

```env
RABBITMQ_URL=amqp://stone:stone@localhost:5672/
RABBITMQ_MGMT_URL=http://localhost:15672
PORTAL_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://10.1.1.190:5173,https://stone.pequenocotolengo.org.br
STONE_EXTRACAO_BASE_URL=http://127.0.0.1:8000
```

```powershell
cd tasy-insercao
poetry install
poetry run python -m tasy_insercao.db up
poetry run python -m tasy_insercao.db status

cd ..\stone-extracao
poetry install

cd ..\portal-controle
npm install
npm run build
```

## 4) Serviços Windows (NSSM — sobe no boot, sem terminal)

1. Baixe NSSM → extraia em `C:\Tools\nssm` (use `win64\nssm.exe`).
2. PowerShell **Admin**:

```powershell
cd C:\GHR_Tech\integracao-tasy-stone
.\deploy\windows\install-services.ps1
```

Serviços criados (Auto Start):

| Serviço        | Função              | Porta |
|----------------|---------------------|-------|
| `StoneExtracao`| API + webhook + cron| 8000  |
| `TasyConsumer` | Consumer Rabbit→Tasy | —   |
| `TasyPainel`   | API do portal       | 8001  |
| `StonePortal`  | Front estático      | 5173  |

Logs: `deploy\windows\logs\`

```powershell
Get-Service StoneExtracao, TasyConsumer, TasyPainel, StonePortal
# reiniciar um:
Restart-Service StoneExtracao
# remover todos:
.\deploy\windows\uninstall-services.ps1
```

## 5) Proxy do subdomínio (TI)

- `/` → portal (`:5173` ou IIS apontando para `portal-controle\dist`)
- `/api`, `/health` → `http://127.0.0.1:8001`
- `/pix`, `/cartao`, `/scheduler` → `http://127.0.0.1:8000`

## 6) Checklist

- [ ] http://127.0.0.1:8000/health
- [ ] http://127.0.0.1:8001/health
- [ ] http://127.0.0.1:5173 (login portal)
- [ ] Reiniciar VM e conferir se os 4 serviços + RabbitMQ voltam sozinhos
- [ ] Scheduler cartão (admin) quando for usar D-1
- [ ] PIX webhook só após HTTPS público + register

## Credenciais

Nunca commitar `.env`. Rotacionar `PORTAL_ADMIN_PASS` e `PORTAL_JWT_SECRET` na VM.

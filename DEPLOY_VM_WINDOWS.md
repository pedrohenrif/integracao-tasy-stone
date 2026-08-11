# Deploy VM Windows (Cotolengo)

Guia para clonar e subir na VM (`10.1.1.190` / portal interno `http://stone.financeiro:5173` / webhook `https://stone.pequenocotolengo.org.br`).

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
PORTAL_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://10.1.1.190:5173,http://stone.financeiro:5173,https://stone.pequenocotolengo.org.br
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

### Reiniciar / verificar serviços (PowerShell Admin)

O `nssm` costuma **não** estar no PATH. Prefira os cmdlets do Windows:

```powershell
# Status
Get-Service StoneExtracao, TasyConsumer, TasyPainel, StonePortal

# Reiniciar um
Restart-Service TasyPainel
Restart-Service StonePortal

# Reiniciar os quatro
Get-Service StoneExtracao, TasyConsumer, TasyPainel, StonePortal | Restart-Service -Force
```

Quando reiniciar o quê:

| Mudança no código / config | Reiniciar |
|----------------------------|-----------|
| Portal (front, `allowedHosts`, Usuários UI) | `StonePortal` |
| API do portal (usuários, CORS, cadastros) | `TasyPainel` |
| Consumer / insert Tasy | `TasyConsumer` |
| Extração Stone / webhook / cron | `StoneExtracao` |
| `.env` do `tasy-insercao` | `TasyPainel` (+ `TasyConsumer` se afetar o worker) |
| `.env` do `stone-extracao` | `StoneExtracao` |

Se tiver o caminho do NSSM:

```powershell
& "C:\Tools\nssm\nssm-2.24\win64\nssm.exe" restart TasyPainel
& "C:\Tools\nssm\nssm-2.24\win64\nssm.exe" restart StonePortal
```

Remover todos os serviços:

```powershell
.\deploy\windows\uninstall-services.ps1
```

## 5) URLs e proxy (TI)

**Portal (rede interna do hospital):**

- `http://stone.financeiro:5173` — DNS interno → VM `10.1.1.190:5173`
- Alternativa: `http://10.1.1.190:5173`

No `portal-controle/vite.config.ts`, o host `stone.financeiro` deve estar em `allowedHosts`.  
No `.env` do `tasy-insercao`, incluir `http://stone.financeiro:5173` em `PORTAL_CORS_ORIGINS`.

**Webhook PIX (internet / Stone):**

- `https://stone.pequenocotolengo.org.br/pix/webhook` → `:8000`

Proxy público (se usado):

- `/` → portal (`:5173` ou IIS apontando para `portal-controle\dist`)
- `/api`, `/health` → `http://127.0.0.1:8001`
- `/pix`, `/cartao`, `/scheduler` → `http://127.0.0.1:8000`

## 6) Checklist

- [ ] http://127.0.0.1:8000/health
- [ ] http://127.0.0.1:8001/health
- [ ] http://127.0.0.1:5173 ou http://stone.financeiro:5173 (login portal)
- [ ] Reiniciar VM e conferir se os 4 serviços + RabbitMQ voltam sozinhos
- [ ] Scheduler cartão (admin) quando for usar D-1
- [ ] Scheduler PIX D-1 (admin) — webhook HTTPS já cadastrado
- [ ] PIX webhook só após HTTPS público + register
- [ ] Admin cria usuário Financeiro em **Usuários**

### Crons D-1 (homolog / produção)

| Fluxo | Horário (.env) | Painel | O que faz |
|-------|----------------|--------|-----------|
| Cartão | `CARTAO_CRON_*` + `CARTAO_CRON_RETRY_*` | Scheduler → Cartão | Extrai XML D-1 → fila (padrão 01:00 e 04:00) |
| PIX | `PIX_CRON_*` + `PIX_CRON_RETRY_*` | Scheduler → PIX | Solicita extrato D-1 → webhook (padrão 01:05 e 04:05) |

Jobs usam `misfire_grace_time` de 2h: se o serviço estiver reiniciando no minuto exato, ainda tentam rodar.  
Diagnóstico PIX/dashboard: `stone-extracao.err.log` — buscar `PIX request` / `SolicitarExtratoPix` / `Webhook PIX` / `reprocessar_dia | PIX`.

Após alterar código do cron: `Restart-Service StoneExtracao` (e `TasyPainel` / `StonePortal` se mudou o painel).

No `.env` do `tasy-insercao` na VM use `APP_ENV=homolog` (ou `production`).  
**Não** use `local`/`dev` no serviço Windows — isso liga `--reload` e pode causar `Failed to fetch` no portal.

## Credenciais

Nunca commitar `.env`. Rotacionar `PORTAL_ADMIN_PASS` e `PORTAL_JWT_SECRET` na VM.

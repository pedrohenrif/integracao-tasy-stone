# DB staging (Postgres) — estilo Prisma

Arquivos:

| Arquivo | Uso |
|---------|-----|
| `schema.sql` | Tabelas Cotolengo (`bandeiras`, `tipos_transacoes`, mapeamento, caixas…) |
| `seed.sql` | Dados reais de homolog (bandeiras, tipos, mapeamento Tasy, caixas) |
| `seed_maquininhas.example.sql` | Referência da lista máquina→setor (dados em `seed.sql`) |

Models SQLAlchemy: `src/tasy_insercao/infrastructure/persistence/models.py`

## Comandos

```powershell
cd tasy-insercao
copy .env.example .env
# preencher POSTGRES_*

poetry install
poetry run python -m tasy_insercao.db up       # schema + seed
poetry run python -m tasy_insercao.db status
```

## O que o seed já traz

- Bandeiras / tipos / mapeamento Tasy  
- Caixas (11…53)  
- **31 maquininhas** (14 ativas `A` da lista TI + Mix 2, resto Churrasco `I`)
- Recepção / Tmkt / Financeiro: `cd_transacao_financeira` provisório — confirmar no Tasy

Consumer só resolve terminal com `ie_status = 'A'`.

```powershell
poetry run python -m tasy_insercao.db up
poetry run python -m tasy_insercao.db status
```

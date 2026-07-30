# DB staging (Postgres) — estilo Prisma

Arquivos:

| Arquivo | Uso |
|---------|-----|
| `schema.sql` | Tabelas Cotolengo (`bandeiras`, `tipos_transacoes`, mapeamento, caixas…) |
| `seed.sql` | Dados reais de homolog (bandeiras, tipos, mapeamento Tasy, caixas) |
| `seed_maquininhas.example.sql` | Exemplo de terminais — **ainda precisa preencher** |

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
- **23 maquininhas** (6 ativas `A`, resto Churrasco `I`)

Consumer só resolve terminal com `ie_status = 'A'`.

```powershell
poetry run python -m tasy_insercao.db up
poetry run python -m tasy_insercao.db status
```

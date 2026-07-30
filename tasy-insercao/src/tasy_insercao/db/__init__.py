from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from tasy_insercao.infrastructure.config.logging import get_logger, setup_logging
from tasy_insercao.infrastructure.config.settings import settings

logger = get_logger(__name__)

# tasy-insercao/db  (repo root of service)
DB_DIR = Path(__file__).resolve().parents[3] / "db"


def _require_pg() -> None:
    if not settings.POSTGRES_DB or not settings.POSTGRES_HOST:
        raise SystemExit(
            "POSTGRES_* não configurado. Preencha tasy-insercao/.env e tente de novo."
        )


def _run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    sql = path.read_text(encoding="utf-8")
    logger.info("Executando %s", path.name)
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def cmd_schema() -> None:
    _require_pg()
    with psycopg.connect(settings.postgres_url) as conn:
        _run_sql_file(conn, DB_DIR / "schema.sql")
        portal = DB_DIR / "schema_portal.sql"
        if portal.is_file():
            _run_sql_file(conn, portal)
    logger.info("Schema OK")


def cmd_seed(file: str | None = None) -> None:
    _require_pg()
    path = Path(file) if file else DB_DIR / "seed.sql"
    if not path.is_absolute():
        # relativo à pasta do serviço ou cwd
        candidates = [path, DB_DIR / path.name, Path.cwd() / path]
        path = next((p for p in candidates if p.is_file()), path)
    with psycopg.connect(settings.postgres_url) as conn:
        _run_sql_file(conn, path)
    logger.info("Seed OK | %s", path)


def cmd_up() -> None:
    """Equivalente rápido a prisma migrate/db push + seed."""
    cmd_schema()
    cmd_seed()
    logger.info("DB up concluído (bandeiras, mapeamento, caixas, maquininhas).")



def cmd_status() -> None:
    _require_pg()
    with psycopg.connect(settings.postgres_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'bandeiras',
                    'tipos_transacoes',
                    'caixas_tasy',
                    'maquininha_stone',
                    'mapeamento_transacoes_tasy',
                    'registro_maquininha'
                  )
                ORDER BY 1
                """
            )
            tables = [r[0] for r in cur.fetchall()]
            print("Tabelas:", ", ".join(tables) if tables else "(nenhuma)")

            if "bandeiras" in tables:
                cur.execute("SELECT COUNT(*) FROM bandeiras")
                print(f"Bandeiras: {cur.fetchone()[0]}")
            if "tipos_transacoes" in tables:
                cur.execute("SELECT COUNT(*) FROM tipos_transacoes")
                print(f"Tipos: {cur.fetchone()[0]}")
            if "mapeamento_transacoes_tasy" in tables:
                cur.execute(
                    """
                    SELECT COUNT(*), COUNT(cd_cartao_bandeira_tasy)
                    FROM mapeamento_transacoes_tasy
                    """
                )
                total, preenchidos = cur.fetchone()
                print(f"Mapeamentos: {total} linhas | com id Tasy: {preenchidos}")
            if "caixas_tasy" in tables:
                cur.execute("SELECT COUNT(*) FROM caixas_tasy")
                print(f"Caixas: {cur.fetchone()[0]}")
            if "maquininha_stone" in tables:
                cur.execute(
                    """
                    SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE ie_status = 'A')
                    FROM maquininha_stone
                    """
                )
                total, ativas = cur.fetchone()
                print(f"Maquininhas: {total} | ativas: {ativas}")


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="tasy_insercao.db",
        description="Gerencia schema/seed do Postgres staging (estilo Prisma db push)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("up", help="Cria tabelas + seed de mapeamento")
    sub.add_parser("schema", help="Só cria/atualiza tabelas (IF NOT EXISTS)")
    p_seed = sub.add_parser("seed", help="Roda seed.sql (ou --file)")
    p_seed.add_argument("--file", help="Arquivo SQL alternativo")
    sub.add_parser("status", help="Mostra estado das tabelas de staging")

    args = parser.parse_args(argv)
    if args.command == "up":
        cmd_up()
    elif args.command == "schema":
        cmd_schema()
    elif args.command == "seed":
        cmd_seed(args.file)
    elif args.command == "status":
        cmd_status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

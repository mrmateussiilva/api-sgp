"""
Script para esvaziar as tabelas do MySQL remoto (PWA) em ambiente de desenvolvimento.

Requisitos:
- Variáveis no .env: DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME

Uso:
  uv run python scripts/empty_mysql_remote.py --force
  uv run python scripts/empty_mysql_remote.py --dry-run  # só mostra o que seria feito
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text, create_engine
from sqlalchemy.engine import URL

from config import settings

LOGGER = logging.getLogger("empty_mysql_remote")

# Ordem: imagens primeiro (detalhe), depois pedidos, depois usuários
TABLES = ["pwa_pedido_imagens", "pwa_pedidos", "pwa_users"]


def _build_mysql_url() -> str:
    if not all([settings.DB_USER, settings.DB_PASS, settings.DB_HOST, settings.DB_NAME]):
        raise ValueError(
            "DB_USER, DB_PASS, DB_HOST e DB_NAME precisam estar configurados no .env"
        )
    return URL.create(
        drivername="mysql+pymysql",
        username=settings.DB_USER,
        password=settings.DB_PASS,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={"charset": "utf8mb4"},
    ).render_as_string(hide_password=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Esvazia as tabelas pwa_* do MySQL remoto (uso em desenvolvimento)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Executar sem confirmação interativa",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas listar as tabelas que seriam truncadas (não executa)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        mysql_url = _build_mysql_url()
    except ValueError as e:
        LOGGER.error("%s", e)
        sys.exit(1)

    if args.dry_run:
        LOGGER.info("Dry-run: as seguintes tabelas seriam truncadas:")
        for t in TABLES:
            LOGGER.info("  - %s", t)
        LOGGER.info("Banco: %s@%s:%s/%s", settings.DB_USER, settings.DB_HOST, settings.DB_PORT, settings.DB_NAME)
        return

    if not args.force:
        print(
            f"Você está prestes a esvaziar as tabelas {TABLES} em\n"
            f"  {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}\n"
        )
        resp = input("Digite 'sim' para confirmar: ").strip().lower()
        if resp != "sim":
            LOGGER.info("Operação cancelada.")
            return

    engine = create_engine(mysql_url, pool_pre_ping=True)
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"TRUNCATE TABLE `{table}`"))
            LOGGER.info("Tabela esvaziada: %s", table)

    LOGGER.info("Banco remoto esvaziado com sucesso.")


if __name__ == "__main__":
    main()

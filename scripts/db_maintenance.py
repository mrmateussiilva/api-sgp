#!/usr/bin/env python3
"""
Tarefas básicas de manutenção para o banco SQLite da API.

Uso básico:
    python scripts/db_maintenance.py
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from scripts.db_utils import resolve_sqlite_path


def human_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.2f}{unit}"
        size /= 1024
    return f"{size:.2f}TB"


def run_integrity_check(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check;").fetchall()
    if len(result) == 1 and result[0][0] == "ok":
        print("[maintenance] PRAGMA integrity_check => ok")
        return

    print("[maintenance] Falha no integrity_check:")
    for row in result:
        print("  -", row[0])
    raise SystemExit(1)


def run_vacuum(connection: sqlite3.Connection) -> None:
    print("[maintenance] Executando VACUUM ...")
    connection.execute("VACUUM;")
    print("[maintenance] VACUUM concluído.")


def run_analyze(connection: sqlite3.Connection) -> None:
    print("[maintenance] Executando ANALYZE ...")
    connection.execute("ANALYZE;")
    print("[maintenance] ANALYZE concluído.")


def run_optimize(connection: sqlite3.Connection) -> None:
    print("[maintenance] Executando PRAGMA optimize ...")
    connection.execute("PRAGMA optimize;")
    print("[maintenance] PRAGMA optimize concluído.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manutenção do banco SQLite.")
    parser.add_argument(
        "--no-vacuum",
        action="store_true",
        help="Não executa VACUUM após o integrity_check.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Executa ANALYZE para atualizar estatísticas.",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Executa PRAGMA optimize ao final.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_sqlite_path()
    print(f"[maintenance] Banco alvo: {db_path} ({human_size(db_path)})")

    connection = sqlite3.connect(db_path)
    try:
        run_integrity_check(connection)
        if not args.no_vacuum:
            run_vacuum(connection)
        if args.analyze:
            run_analyze(connection)
        if args.optimize:
            run_optimize(connection)
    finally:
        connection.close()

    print("[maintenance] Manutenção concluída com sucesso.")


if __name__ == "__main__":
    main()

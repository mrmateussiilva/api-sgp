#!/usr/bin/env python3
"""
Cria um backup consistente do banco SQLite configurado em settings.DATABASE_URL.

Uso básico:
    python scripts/backup_database.py
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scripts.db_utils import PROJECT_ROOT, resolve_sqlite_path

DEFAULT_DESTINATION = PROJECT_ROOT / "backups" / "db"


def sqlite_backup(source: Path, destination: Path) -> None:
    """Usa a API de backup oficial do SQLite para garantir consistência."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source}?mode=ro"
    src_conn = sqlite3.connect(source_uri, uri=True)
    dest_conn = sqlite3.connect(destination)
    try:
        with dest_conn:
            src_conn.backup(dest_conn)
    finally:
        src_conn.close()
        dest_conn.close()


def prune_old_backups(directory: Path, retention: Optional[int]) -> int:
    """Remove backups mais antigos que excedem o limite de retenção."""
    if not retention or retention <= 0:
        return 0

    backups = sorted(
        [p for p in directory.glob("*.db") if p.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for obsolete in backups[retention:]:
        obsolete.unlink(missing_ok=True)
        removed += 1
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup do banco SQLite da API.")
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DESTINATION,
        help=f"Diretório de destino (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=10,
        help="Número máximo de arquivos de backup a manter (0 para desativar limpeza).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_sqlite_path()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_name = f"{db_path.stem}-{timestamp}.db"
    destination_file = args.dest / backup_name

    print(f"[backup] Banco origem: {db_path}")
    print(f"[backup] Destino: {destination_file}")
    sqlite_backup(db_path, destination_file)
    print("[backup] Backup concluído com sucesso.")

    removed = prune_old_backups(args.dest, args.retention)
    if removed:
        print(f"[backup] Limpeza: {removed} backup(s) antigo(s) removido(s).")


if __name__ == "__main__":
    main()

"""
Utilidades compartilhadas para scripts administrativos do banco de dados.
"""
from __future__ import annotations

from pathlib import Path
from typing import Final

from config import settings

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent


def resolve_sqlite_path() -> Path:
    """
    Resolve o caminho físico do arquivo SQLite definido em settings.DATABASE_URL.

    Retorna:
        Path absoluto para o arquivo do banco de dados.

    Levanta:
        RuntimeError se o DATABASE_URL não for baseado em SQLite.
    """
    database_url = settings.DATABASE_URL
    if not database_url.startswith("sqlite://"):
        raise RuntimeError(
            "Os scripts de manutenção atuais suportam apenas DATABASE_URL baseado em SQLite."
        )

    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "", 1)
    else:
        db_path = database_url.replace("sqlite://", "", 1)

    path = Path(db_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path

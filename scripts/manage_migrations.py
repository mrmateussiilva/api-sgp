"""
CLI operacional para migrations via Alembic.

Uso comum:
    python scripts/manage_migrations.py status
    python scripts/manage_migrations.py upgrade
    python scripts/manage_migrations.py downgrade -1
    python scripts/manage_migrations.py history
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = ROOT_DIR / "alembic.ini"


def load_alembic():
    try:
        from alembic import command
        from alembic.config import Config
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Alembic nao esta disponivel neste ambiente. Rode com 'uv run' "
            "ou usando a .venv da release."
        ) from exc
    return command, Config


def build_config():
    _, Config = load_alembic()
    os.chdir(ROOT_DIR)
    sys.path.insert(0, str(ROOT_DIR))
    return Config(str(ALEMBIC_INI))


def cmd_status(config) -> int:
    command, _ = load_alembic()
    print("== Revisao atual ==")
    command.current(config, verbose=True)
    print("\n== Heads disponiveis ==")
    command.heads(config, verbose=True)
    return 0


def cmd_history(config) -> int:
    command, _ = load_alembic()
    command.history(config, verbose=True)
    return 0


def cmd_upgrade(config, revision: str) -> int:
    command, _ = load_alembic()
    print(f"Aplicando migrations ate: {revision}")
    command.upgrade(config, revision)
    return 0


def cmd_downgrade(config, revision: str) -> int:
    command, _ = load_alembic()
    print(f"Revertendo migrations ate: {revision}")
    command.downgrade(config, revision)
    return 0


def cmd_revision(config, message: str, autogenerate: bool) -> int:
    command, _ = load_alembic()
    if not message.strip():
        raise ValueError("A mensagem da migration nao pode ser vazia.")
    command.revision(config, message=message, autogenerate=autogenerate)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gerencia migrations Alembic da API.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Mostra revisao atual e heads disponiveis.")
    subparsers.add_parser("history", help="Mostra historico de migrations.")

    upgrade_parser = subparsers.add_parser("upgrade", help="Aplica migrations.")
    upgrade_parser.add_argument(
        "revision",
        nargs="?",
        default="head",
        help="Revisao de destino. Padrao: head",
    )

    downgrade_parser = subparsers.add_parser("downgrade", help="Reverte migrations.")
    downgrade_parser.add_argument(
        "revision",
        help='Revisao de destino, por exemplo "-1" ou um revision id.',
    )

    revision_parser = subparsers.add_parser("revision", help="Cria nova migration.")
    revision_parser.add_argument("-m", "--message", required=True, help="Descricao da migration.")
    revision_parser.add_argument(
        "--autogenerate",
        action="store_true",
        help="Gera migration comparando metadata e banco.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = build_config()

    try:
        if args.command == "status":
            return cmd_status(config)
        if args.command == "history":
            return cmd_history(config)
        if args.command == "upgrade":
            return cmd_upgrade(config, args.revision)
        if args.command == "downgrade":
            return cmd_downgrade(config, args.revision)
        if args.command == "revision":
            return cmd_revision(config, args.message, args.autogenerate)
    except Exception as exc:
        print(f"Erro ao executar migration: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

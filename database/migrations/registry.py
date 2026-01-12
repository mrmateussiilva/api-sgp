"""
Registry de migrations.
Todas as migrations devem ser importadas e registradas aqui.
"""
from typing import List, Type
from .base import Migration


# Importar todas as migrations
# IMPORTANTE: Sempre importar na ordem correta (001, 002, 003...)
from .m001_initial_schema import Migration001_InitialSchema
# Adicionar novas migrations aqui:
# from .m002_add_revoked_tokens import Migration002_AddRevokedTokens


# Lista de migrations em ordem (IMPORTANTE: manter ordem)
MIGRATIONS: List[Type[Migration]] = [
    Migration001_InitialSchema,
    # Adicionar novas migrations aqui:
    # Migration002_AddRevokedTokens,
]


def get_migration_by_version(version: str) -> Type[Migration] | None:
    """Encontra uma migration pelo número de versão"""
    for migration_class in MIGRATIONS:
        migration_instance = migration_class()
        if migration_instance.version == version:
            return migration_class
    return None


def get_all_migrations() -> List[Type[Migration]]:
    """Retorna todas as migrations em ordem"""
    return MIGRATIONS.copy()

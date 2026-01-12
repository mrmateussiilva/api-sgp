"""
Script para executar migrations do banco de dados.
"""
import asyncio
import sys
import logging
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.migrations.base import ensure_migrations_table, get_applied_migrations
from database.migrations.registry import MIGRATIONS
from database.database import async_session_maker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations(dry_run: bool = False) -> bool:
    """
    Executa todas as migrations pendentes.
    
    Args:
        dry_run: Se True, apenas mostra o que seria feito, sem aplicar
    
    Returns:
        True se sucesso, False se erro
    """
    await ensure_migrations_table()
    
    async with async_session_maker() as session:
        applied_versions = await get_applied_migrations(session)
        logger.info(f"Migrations aplicadas: {applied_versions}")
        
        pending_migrations = []
        for migration_class in MIGRATIONS:
            migration = migration_class()
            if migration.version not in applied_versions:
                pending_migrations.append(migration)
        
        if not pending_migrations:
            logger.info("✅ Nenhuma migration pendente")
            return True
        
        logger.info(f"📋 {len(pending_migrations)} migration(s) pendente(s)")
        
        if dry_run:
            logger.info("🔍 DRY RUN - Nenhuma alteração será feita")
            for migration in pending_migrations:
                logger.info(f"  - {migration.version}: {migration.name} - {migration.description}")
            return True
        
        # Aplicar migrations pendentes
        for migration in pending_migrations:
            try:
                logger.info(f"🔄 Aplicando migration {migration.version}: {migration.name}...")
                await migration.upgrade(session)
                await migration.mark_applied(session)
                logger.info(f"✅ Migration {migration.version} aplicada com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao aplicar migration {migration.version}: {e}", exc_info=True)
                await session.rollback()
                return False
        
        logger.info("✅ Todas as migrations foram aplicadas com sucesso")
        return True


async def rollback_migration(version: str) -> bool:
    """
    Reverte uma migration específica.
    
    Args:
        version: Versão da migration a reverter (ex: "002")
    
    Returns:
        True se sucesso, False se erro
    """
    await ensure_migrations_table()
    
    from database.migrations.registry import get_migration_by_version
    
    migration_class = get_migration_by_version(version)
    if not migration_class:
        logger.error(f"❌ Migration {version} não encontrada")
        return False
    
    async with async_session_maker() as session:
        migration = migration_class()
        
        if not await migration.is_applied(session):
            logger.warning(f"⚠️ Migration {version} não foi aplicada")
            return False
        
        try:
            logger.info(f"🔄 Revertendo migration {version}: {migration.name}...")
            await migration.downgrade(session)
            await migration.mark_unapplied(session)
            logger.info(f"✅ Migration {version} revertida com sucesso")
            return True
        except NotImplementedError as e:
            logger.error(f"❌ Migration {version} não pode ser revertida: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao reverter migration {version}: {e}", exc_info=True)
            await session.rollback()
            return False


async def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Executar migrations do banco de dados")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostrar o que seria feito, sem aplicar"
    )
    parser.add_argument(
        "--rollback",
        type=str,
        help="Reverter migration específica (ex: --rollback 002)"
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        success = await rollback_migration(args.rollback)
        sys.exit(0 if success else 1)
    else:
        success = await run_migrations(dry_run=args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

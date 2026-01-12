"""
Migration 001: Schema inicial do banco.
Esta migration marca o estado inicial do banco de dados.
Não faz alterações - apenas marca como "baseline".
"""
from .base import Migration
from sqlmodel.ext.asyncio.session import AsyncSession


class Migration001_InitialSchema(Migration):
    """Migration inicial - baseline do schema atual"""
    
    version = "001"
    name = "initial_schema"
    description = "Schema inicial do banco de dados (baseline)"
    
    async def upgrade(self, session: AsyncSession) -> None:
        """
        Esta migration não faz alterações.
        Apenas marca o estado inicial do banco.
        SQLModel cria tabelas automaticamente via create_db_and_tables().
        """
        # Não fazer nada - SQLModel cria tabelas automaticamente
        pass
    
    async def downgrade(self, session: AsyncSession) -> None:
        """
        Não há como reverter o schema inicial.
        Isso destruiria todos os dados.
        """
        raise NotImplementedError("Não é possível reverter migration inicial")

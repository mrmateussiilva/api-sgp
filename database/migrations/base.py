"""
Base para sistema de migrations simples.
Gerencia aplicação e reversão de migrations para SQLite.
"""
import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import text
from sqlmodel import SQLModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from database.database import engine

logger = logging.getLogger(__name__)


class MigrationRecord(SQLModel, table=True):
    """Tabela para rastrear migrations aplicadas"""
    __tablename__ = "_migrations"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    version: str = Field(unique=True, index=True)
    name: str
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = None


class Migration:
    """Classe base para migrations"""
    
    version: str  # Ex: "001", "002"
    name: str  # Ex: "create_revoked_tokens_table"
    description: str = ""  # Descrição opcional
    
    async def upgrade(self, session: AsyncSession) -> None:
        """
        Aplica a migration.
        Deve implementar as mudanças no banco de dados.
        """
        raise NotImplementedError("Subclasses devem implementar upgrade()")
    
    async def downgrade(self, session: AsyncSession) -> None:
        """
        Reverte a migration.
        Deve implementar a reversão das mudanças.
        Opcional: pode ser NotImplementedError se irreversível.
        """
        raise NotImplementedError("Subclasses devem implementar downgrade()")
    
    async def is_applied(self, session: AsyncSession) -> bool:
        """Verifica se a migration já foi aplicada"""
        statement = text("SELECT COUNT(*) FROM _migrations WHERE version = :version")
        result = await session.execute(statement, {"version": self.version})
        count = result.scalar()
        return count > 0
    
    async def mark_applied(self, session: AsyncSession) -> None:
        """Marca a migration como aplicada"""
        record = MigrationRecord(
            version=self.version,
            name=self.name,
            description=self.description,
            applied_at=datetime.utcnow()
        )
        session.add(record)
        await session.commit()
    
    async def mark_unapplied(self, session: AsyncSession) -> None:
        """Remove o registro da migration (para rollback)"""
        statement = text("DELETE FROM _migrations WHERE version = :version")
        await session.execute(statement, {"version": self.version})
        await session.commit()


async def ensure_migrations_table() -> None:
    """Garante que a tabela _migrations existe"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, checkfirst=True)


async def get_applied_migrations(session: AsyncSession) -> List[str]:
    """Retorna lista de versões de migrations aplicadas"""
    statement = text("SELECT version FROM _migrations ORDER BY version")
    result = await session.execute(statement)
    return [row[0] for row in result.fetchall()]


async def get_latest_migration_version(session: AsyncSession) -> Optional[str]:
    """Retorna a versão da migration mais recente aplicada"""
    statement = text("SELECT MAX(version) FROM _migrations")
    result = await session.execute(statement)
    version = result.scalar()
    return version

"""
Configuração global de testes para o backend SGP.
Fornece fixtures para banco de dados em memória e cliente HTTP.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from main import app
from database.database import get_session


# URL do banco de dados em memória para testes
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Cria um engine SQLite em memória para cada teste."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    
    # Criar todas as tabelas
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # Garantir schema de pedidos (colunas e índices) usando o engine de teste
    from sqlalchemy import text
    async with engine.begin() as conn:
        # Verificar e adicionar colunas necessárias
        columns_result = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(text("PRAGMA table_info(pedidos)")).fetchall()
        )
        existing_columns = {col[1] for col in columns_result}
        
        required_columns = {
            'conferencia': "ALTER TABLE pedidos ADD COLUMN conferencia BOOLEAN DEFAULT 0",
            'sublimacao_maquina': "ALTER TABLE pedidos ADD COLUMN sublimacao_maquina TEXT",
            'sublimacao_data_impressao': "ALTER TABLE pedidos ADD COLUMN sublimacao_data_impressao TEXT",
            'pronto': "ALTER TABLE pedidos ADD COLUMN pronto BOOLEAN DEFAULT 0",
        }
        
        for col_name, ddl in required_columns.items():
            if col_name not in existing_columns:
                await conn.execute(text(ddl))
        
        # Criar índices
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_numero ON pedidos(numero)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_data_entrada ON pedidos(data_entrada)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_data_entrega ON pedidos(data_entrega)",
            "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente)",
        ]
        for index_ddl in indexes:
            await conn.execute(text(index_ddl))
    
    yield engine
    
    # Limpar após o teste
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine):
    """Cria uma sessão de banco de dados para cada teste."""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_session):
    """Cria um cliente HTTP assíncrono para testes."""
    async def override_get_session():
        yield test_session
    
    # Substituir a dependência get_session pela sessão de teste
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    # Limpar override após o teste
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def clean_db(test_session):
    """Garante que o banco está limpo antes de cada teste."""
    # Limpar todas as tabelas
    from sqlalchemy import text
    
    async with test_session.begin():
        # Desabilitar foreign keys temporariamente
        await test_session.execute(text("PRAGMA foreign_keys = OFF"))
        
        # Listar todas as tabelas e deletar dados
        result = await test_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        tables = [row[0] for row in result.fetchall()]
        
        for table in tables:
            await test_session.execute(text(f"DELETE FROM {table}"))
        
        await test_session.execute(text("PRAGMA foreign_keys = ON"))
        await test_session.commit()
    
    yield test_session


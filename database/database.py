from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from config import settings


def _build_async_database_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


DATABASE_URL = settings.DATABASE_URL
ASYNC_DATABASE_URL = _build_async_database_url(DATABASE_URL)

connect_args = {"timeout": 60} if ASYNC_DATABASE_URL.startswith("sqlite+") else {}

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=15,  # Número de conexões no pool (aumentado para melhor concorrência)
    max_overflow=25,  # Conexões extras permitidas (aumentado para suportar 20 clientes)
    pool_timeout=30,  # Timeout para obter conexão do pool
    pool_recycle=3600,  # Reciclar conexões após 1 hora
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


if engine.sync_engine.url.get_backend_name() == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # WAL mode permite leituras simultâneas
        cursor.execute("PRAGMA journal_mode=WAL;")
        # NORMAL é mais rápido que FULL, ainda seguro
        cursor.execute("PRAGMA synchronous=NORMAL;")
        # Timeout aumentado para 10 segundos
        cursor.execute("PRAGMA busy_timeout=10000;")
        # Cache maior melhora performance de leitura (64MB)
        cursor.execute("PRAGMA cache_size=-64000;")
        # Usar memória para tabelas temporárias
        cursor.execute("PRAGMA temp_store=MEMORY;")
        # Memory-mapped I/O para melhor performance (256MB)
        cursor.execute("PRAGMA mmap_size=268435456;")
        # Otimizar automaticamente
        cursor.execute("PRAGMA optimize;")
        cursor.close()


async def create_db_and_tables():
    """Cria as tabelas no banco de dados"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session():
    """Dependência para injetar sessão nas rotas"""
    async with async_session_maker() as session:
        yield session

from sqlalchemy import event
from sqlmodel import SQLModel, create_engine, Session
from config import settings

DATABASE_URL = settings.DATABASE_URL

connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


if engine.url.get_backend_name() == "sqlite":
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

def create_db_and_tables():
    """Cria as tabelas no banco de dados"""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Dependência para injetar sessão nas rotas"""
    with Session(engine) as session:
        yield session

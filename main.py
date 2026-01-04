from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from base import create_db_and_tables
from config import settings
from logging_config import setup_logging
from auth.security import extract_bearer_token, get_user_from_token

# Routers
from auth.router import router as auth_router
from pedidos.router import router as pedidos_router, ensure_order_schema
from pedidos.realtime import orders_notifier
from clientes.router import router as clientes_router
from pagamentos.router import router as pagamentos_router
from envios.router import router as envios_router
from admin.router import router as admin_router
from materiais.router import router as materiais_router
from designers.router import router as designers_router
from vendedores.router import router as vendedores_router
from producoes.router import router as producoes_router
from users.router import router as users_router
from notificacoes.router import router as notificacoes_router
from fichas.router import router as fichas_router
from relatorios.router import router as relatorios_router

# Importar modelos para garantir que as tabelas sejam criadas
from fichas.schema import Ficha, FichaTemplateModel  # noqa: F401
from relatorios.schema import RelatorioTemplateModel  # noqa: F401
from producoes.schema import Producao  # noqa: F401

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    await ensure_order_schema()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    default_response_class=ORJSONResponse
)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=settings.BACKEND_CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Inclusão dos routers
app.include_router(auth_router, prefix="/auth")
app.include_router(pedidos_router, prefix=settings.API_V1_STR)
app.include_router(clientes_router, prefix=settings.API_V1_STR)
app.include_router(pagamentos_router, prefix=settings.API_V1_STR)
app.include_router(envios_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(materiais_router, prefix=settings.API_V1_STR)
app.include_router(designers_router, prefix=settings.API_V1_STR)
app.include_router(vendedores_router, prefix=settings.API_V1_STR)
app.include_router(producoes_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(notificacoes_router, prefix="/api")
app.include_router(fichas_router, prefix=settings.API_V1_STR)
app.include_router(relatorios_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "API Sistema de Fichas",
        "version": "1.0.1",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """
    Endpoint de verificação de saúde da API
    Usado para verificar se a API está online e respondendo
    """
    return {
        "status": "ok",
        "message": "API is running",
        "version": settings.VERSION
    }


@app.websocket("/ws/orders")
async def orders_websocket(websocket: WebSocket):
    """Canal websocket protegido por token JWT."""
    # Aceitar conexão primeiro
    await websocket.accept()
    
    # Validar token após aceitar
    token = websocket.query_params.get("token")
    if not token:
        token = extract_bearer_token(websocket.headers.get("Authorization"))

    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=1008, reason="Token inválido ou ausente")
        return

    await orders_notifier.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await orders_notifier.disconnect(websocket)
    except Exception:
        await orders_notifier.disconnect(websocket)

import sys
import os
from pathlib import Path

# Se estiver rodando como executável PyInstaller
if getattr(sys, 'frozen', False):
    # Executável PyInstaller
    BASE_DIR = Path(sys._MEIPASS)
    # Diretório de trabalho = onde o .exe está
    WORK_DIR = Path(sys.executable).parent
else:
    # Código Python normal
    BASE_DIR = Path(__file__).parent
    WORK_DIR = BASE_DIR

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)

_load_env_file(WORK_DIR / ".env")

# Determinar diretório raiz da API (para releases compartilhadas)
# Em produção, API_ROOT deve estar definido como variável de ambiente
# Ex: C:\api (Windows) ou /opt/api (Linux)
API_ROOT = os.environ.get("API_ROOT")
if API_ROOT:
    API_ROOT = Path(API_ROOT)
else:
    # Fallback: usar diretório atual (modo desenvolvimento)
    API_ROOT = WORK_DIR

# Diretório compartilhado (fora das releases)
# Todas as versões compartilham: db, media, logs, backups
SHARED_DIR = API_ROOT / "shared"

# Criar estrutura de diretórios compartilhados se não existir
shared_dirs = {
    "db": SHARED_DIR / "db",
    "media": SHARED_DIR / "media",
    "media_pedidos": SHARED_DIR / "media" / "pedidos",
    "media_fichas": SHARED_DIR / "media" / "fichas",
    "media_templates": SHARED_DIR / "media" / "templates",
    "logs": SHARED_DIR / "logs",
    "backups": SHARED_DIR / "backups",
}

for dir_name, dir_path in shared_dirs.items():
    dir_path.mkdir(parents=True, exist_ok=True)

# Configurar variáveis de ambiente para usar diretórios compartilhados
# Isso sobrescreve qualquer configuração anterior
if "API_ROOT" not in os.environ:
    os.environ["API_ROOT"] = str(API_ROOT)
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = f"sqlite:///{SHARED_DIR / 'db' / 'banco.db'}"
if "MEDIA_ROOT" not in os.environ:
    os.environ["MEDIA_ROOT"] = str(SHARED_DIR / "media")
if "LOG_DIR" not in os.environ:
    os.environ["LOG_DIR"] = str(SHARED_DIR / "logs")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from base import create_db_and_tables
from config import settings
from logging_config import setup_logging
from auth.security import extract_bearer_token, get_user_from_token
from middleware.metrics import MetricsMiddleware

# Routers
from auth.router import router as auth_router
from pedidos.router import router as pedidos_router
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
from relatorios_fechamentos.router import router as relatorios_fechamentos_router
from relatorios_envios.router import router as relatorios_envios_router
from reposicoes.router import router as reposicoes_router

# Importar modelos para garantir que as tabelas sejam criadas
from fichas.schema import Ficha, FichaTemplateModel  # noqa: F401
from relatorios.schema import RelatorioTemplateModel  # noqa: F401
from producoes.schema import Producao  # noqa: F401

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    redoc_url="/redoc",
)
# Middleware de métricas - deve ser adicionado primeiro para capturar todo o tempo de processamento
app.add_middleware(MetricsMiddleware)
# GZip com threshold reduzido (100 bytes) para comprimir mais respostas e reduzir tráfego de rede
app.add_middleware(GZipMiddleware, minimum_size=100)

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
#app.include_router(relatorios_router, prefix=settings.API_V1_STR)
app.include_router(relatorios_fechamentos_router, prefix=settings.API_V1_STR)
app.include_router(relatorios_envios_router, prefix=settings.API_V1_STR)
app.include_router(reposicoes_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "API Sistema de Fichas",
        "version": settings.VERSION,
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """
    Endpoint de verificação de saúde da API
    Verifica: API, banco de dados, versão
    """
    from database.database import engine
    from sqlalchemy import text
    from datetime import datetime
    from fastapi import status as http_status
    from fastapi.responses import JSONResponse
    
    status = {
        "status": "ok",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "api": "ok",
            "database": "unknown"
        }
    }
    
    # Verificar banco de dados
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
            status["checks"]["database"] = "ok"
    except Exception as e:
        status["status"] = "degraded"
        status["checks"]["database"] = "error"
        status["database_error"] = str(e)
        # Retornar 503 em caso de erro no banco
        return JSONResponse(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            content=status
        )
    
    return status


@app.websocket("/ws/orders")
async def orders_websocket(websocket: WebSocket):
    """
    Canal websocket protegido por token JWT.
    Permite múltiplas conexões por usuário (ex.: várias abas/PCs com o mesmo login).
    Suporta broadcast de mensagens entre clientes.
    """
    import json
    
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

    user_id = user.id
    # Conectar passando user_id (múltiplas conexões por usuário são permitidas)
    await orders_notifier.connect(websocket, user_id)
    
    try:
        while True:
            # Receber mensagens (pode ser ping/pong ou outras mensagens)
            data = await websocket.receive_text()
            
            # Responder a pings do heartbeat
            if data == '{"type":"ping"}' or data == "ping":
                try:
                    await websocket.send_text('{"type":"pong"}')
                except Exception:
                    # Se não conseguir enviar pong, a conexão está morta
                    break
                continue
            
            # Tentar processar como JSON para broadcast
            try:
                message = json.loads(data)
                
                # Se for mensagem de broadcast, enviar para todos os outros clientes
                if message.get("broadcast") and message.get("type") not in ("ping", "pong"):
                    # Preservar user_id se já existir na mensagem, senão adicionar do remetente
                    if "user_id" not in message:
                        message["user_id"] = user_id
                    if "username" not in message:
                        message["username"] = user.username
                    
                    # Criar mensagem para broadcast (sem flag broadcast para evitar loops)
                    message_to_broadcast = {k: v for k, v in message.items() if k != "broadcast"}
                    
                    # Obter número de clientes conectados (exceto remetente)
                    total_connections = orders_notifier.get_connection_count()
                    # Criar lista temporária para contar outros clientes (sem lock para evitar deadlock)
                    other_connections_count = max(0, total_connections - 1)  # -1 para excluir o remetente
                    
                    if __debug__:
                        print(f"[WebSocket] Recebido broadcast do cliente (user_id={user_id}): type={message.get('type')}, order_id={message.get('order_id')}")
                        print(f"[WebSocket] Total de conexões: {total_connections}, Outros clientes: {other_connections_count}")
                    
                    # Broadcast para todos os outros clientes (exceto o remetente)
                    # O broadcast_except já verifica se há outros clientes, então podemos chamar diretamente
                    await orders_notifier.broadcast_except(message_to_broadcast, exclude_websocket=websocket)
                    if __debug__:
                        print(f"[WebSocket] ✅ Tentativa de broadcast '{message.get('type')}' concluída")
                    
            except json.JSONDecodeError:
                # Mensagem não é JSON válido, ignorar
                pass
                
    except WebSocketDisconnect:
        await orders_notifier.disconnect(websocket)
    except Exception as e:
        if __debug__:
            print(f"[WebSocket] Erro na conexão do usuário {user_id}: {e}")
        await orders_notifier.disconnect(websocket)


# Permite executar o servidor diretamente (útil para executável)
if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="API Sistema de Gestão de Produção (SGP)")
    parser.add_argument("--bind", default="0.0.0.0:8000", help="Endereço e porta (ex: 0.0.0.0:8000)")
    parser.add_argument("--workers", type=int, default=0, help="Número de workers (0 = sem workers)")
    parser.add_argument("--loop", default="asyncio", help="Event loop (asyncio ou uvloop)")
    
    args = parser.parse_args()
    
    # Parse bind address
    if ":" in args.bind:
        host, port = args.bind.rsplit(":", 1)
        port = int(port)
    else:
        host = args.bind
        port = 8000
    
    # Se workers > 0, usar hypercorn (suporta workers no Windows)
    if args.workers > 0:
        try:
            import hypercorn.asyncio
            from hypercorn.config import Config
            
            config = Config()
            config.bind = [f"{host}:{port}"]
            config.workers = args.workers
            config.loop = args.loop
            
            print(f"🚀 Iniciando API SGP com Hypercorn")
            print(f"   Host: {host}")
            print(f"   Porta: {port}")
            print(f"   Workers: {args.workers}")
            print(f"   Loop: {args.loop}")
            print()
            
            hypercorn.asyncio.serve(app, config)
        except ImportError:
            print("⚠️  Hypercorn não encontrado. Usando Uvicorn sem workers.")
            uvicorn.run(app, host=host, port=port, loop=args.loop)
    else:
        print(f"🚀 Iniciando API SGP com Uvicorn")
        print(f"   Host: {host}")
        print(f"   Porta: {port}")
        print()
        uvicorn.run(app, host=host, port=port, loop=args.loop)

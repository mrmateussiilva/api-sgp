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

# Garantir que diretórios necessários existam no diretório do executável
for dir_name in ["db", "media", "logs", "backups"]:
    (WORK_DIR / dir_name).mkdir(exist_ok=True)

# Ajustar variáveis de ambiente se não estiverem definidas
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = f"sqlite:///{WORK_DIR / 'db' / 'banco.db'}"
if "MEDIA_ROOT" not in os.environ:
    os.environ["MEDIA_ROOT"] = str(WORK_DIR / "media")

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
        "version": settings.VERSION,
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

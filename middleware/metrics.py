"""
Middleware para métricas de performance.
Loga tempo de processamento de cada requisição HTTP.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware que loga métricas de performance de cada requisição.
    
    Logs incluem:
    - Método HTTP (GET, POST, etc.)
    - Caminho da rota
    - Status code da resposta
    - Tempo de processamento em segundos
    
    Requisições lentas (>1s) são logadas como WARNING.
    Requisições muito lentas (>3s) são logadas como ERROR.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log de métricas (INFO para todas as requisições)
            logger.info(
                "[METRICS] %s %s - %d - %.3fs",
                request.method,
                request.url.path,
                response.status_code,
                process_time
            )
            
            # Adicionar header com tempo de processamento (útil para debug)
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            # Log de warnings para requisições lentas (>1s)
            if process_time > 1.0:
                logger.warning(
                    "[SLOW_REQUEST] %s %s levou %.3fs para processar",
                    request.method,
                    request.url.path,
                    process_time
                )
            
            # Log de errors para requisições muito lentas (>3s)
            if process_time > 3.0:
                logger.error(
                    "[VERY_SLOW_REQUEST] %s %s levou %.3fs para processar",
                    request.method,
                    request.url.path,
                    process_time
                )
            
            return response
            
        except Exception as exc:
            # Em caso de erro, ainda logar o tempo até o erro
            process_time = time.time() - start_time
            logger.error(
                "[METRICS_ERROR] %s %s - ERROR após %.3fs: %s",
                request.method,
                request.url.path,
                process_time,
                str(exc),
                exc_info=True
            )
            raise

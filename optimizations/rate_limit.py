"""
Rate limiting para proteger a API contra abuso e garantir recursos para usuários legítimos.
Usa slowapi para implementação simples e eficiente.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Criar limiter global
limiter = Limiter(key_func=get_remote_address)

# Função para obter IP do cliente (considera proxies)
def get_client_ip(request: Request) -> str:
    """
    Obtém IP do cliente, considerando headers de proxy (X-Forwarded-For).
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IP do cliente como string
    """
    # Verificar header de proxy primeiro
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Pegar primeiro IP da lista
        return forwarded.split(",")[0].strip()
    
    # Verificar X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback para IP direto
    return get_remote_address(request)

# Limiter customizado com função de IP melhorada
limiter = Limiter(key_func=get_client_ip)

# Limites padrão por endpoint
DEFAULT_LIMITS = {
    "listar_pedidos": "100/minute",  # 100 req/min
    "obter_pedido": "200/minute",    # 200 req/min
    "criar_pedido": "30/minute",     # 30 req/min (escrita)
    "atualizar_pedido": "50/minute", # 50 req/min (escrita)
    "deletar_pedido": "20/minute",   # 20 req/min (escrita)
    "auth_login": "10/minute",       # 10 req/min (segurança)
    "default": "100/minute",         # Limite padrão
}

def get_rate_limit(endpoint_name: str) -> str:
    """
    Obtém limite de rate para um endpoint.
    
    Args:
        endpoint_name: Nome do endpoint
        
    Returns:
        String de limite (ex: "100/minute")
    """
    return DEFAULT_LIMITS.get(endpoint_name, DEFAULT_LIMITS["default"])


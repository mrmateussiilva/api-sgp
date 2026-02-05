"""
Script temporário para debugar erro 422 de validação.
Adicione este middleware ao main.py para capturar erros de validação detalhados.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler customizado para erros de validação que loga os detalhes completos.
    """
    logger.error(f"Erro de validação em {request.method} {request.url.path}")
    logger.error(f"Detalhes do erro: {exc.errors()}")
    logger.error(f"Body recebido: {exc.body}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": str(exc.body)[:500]  # Primeiros 500 chars do body
        },
    )

# Adicione ao main.py:
# from debug_validation import validation_exception_handler
# from fastapi.exceptions import RequestValidationError
# app.add_exception_handler(RequestValidationError, validation_exception_handler)

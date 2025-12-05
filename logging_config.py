"""
Configuração simples de logging centralizado para a API.
"""
import logging
from typing import Optional

from config import settings


def setup_logging(level: Optional[str] = None) -> None:
    """Inicializa logging estruturado para toda a aplicação."""
    resolved_level = (level or settings.LOG_LEVEL or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

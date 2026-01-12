"""
Configuração de logging centralizado para a API.
Salva logs em arquivo com rotação diária.
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from config import settings


def setup_logging(level: Optional[str] = None) -> None:
    """
    Inicializa logging estruturado para toda a aplicação.
    
    Configura:
    - Logs salvos em arquivo (um arquivo por dia)
    - Rotação diária à meia-noite
    - Mantém logs antigos por 30 dias
    - Formato: api.log.YYYY-MM-DD
    - Logs também aparecem no terminal (se não estiver rodando como serviço)
    """
    resolved_level = (level or settings.LOG_LEVEL or "INFO").upper()
    
    # Determinar diretório de logs
    # LOG_DIR pode estar definido como variável de ambiente pelo main.py
    log_dir = Path(os.environ.get("LOG_DIR", settings.LOG_DIR))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Caminho do arquivo de log
    log_file = log_dir / "api.log"
    
    # Formato de log
    log_format = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, resolved_level, logging.INFO))
    
    # Remover handlers existentes (para evitar duplicação)
    root_logger.handlers.clear()
    
    # Handler para arquivo com rotação diária
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",  # Rotação à meia-noite
        interval=1,  # Diariamente
        backupCount=30,  # Manter 30 dias de logs
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, resolved_level, logging.INFO))
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    file_handler.suffix = "%Y-%m-%d"  # Formato do sufixo: YYYY-MM-DD
    
    # Handler para console (terminal) - útil em desenvolvimento
    # Em produção como serviço, o serviço já captura stdout/stderr
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, resolved_level, logging.INFO))
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Adicionar handlers ao root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log inicial para confirmar configuração (só aparece no console se não tiver sido logado antes)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configurado: nível={resolved_level}, arquivo={log_file}, rotação=diária")

"""
Utilitário para salvar imagens base64 de fichas.
Compatível com Windows e Linux usando pathlib.
Versão robusta para produção com validações e segurança.
"""

from __future__ import annotations

import base64
import binascii
import logging
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from config import settings

# Configurar logger
logger = logging.getLogger(__name__)

# Caminho raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Configurar MEDIA_ROOT (compatível com Windows e Linux)
_configured_media_root = Path(settings.MEDIA_ROOT)
if not _configured_media_root.is_absolute():
    MEDIA_ROOT = (PROJECT_ROOT / _configured_media_root).resolve()
else:
    MEDIA_ROOT = _configured_media_root.resolve()

# Diretório para imagens de fichas
FICHAS_MEDIA_ROOT = MEDIA_ROOT / "fichas"
FICHAS_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Tamanho máximo de imagem: 5MB
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024

# Dimensões máximas de imagem (em pixels)
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096

# Magic bytes para validação de tipo de arquivo
IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'png',
    b'\xff\xd8\xff': 'jpeg',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'BM': 'bmp',
    b'RIFF': 'webp',  # WebP começa com RIFF, mas precisa verificar mais
}


class ImageStorageError(ValueError):
    """Erro ao processar ou salvar imagem."""


def _validate_image_type(binary_data: bytes) -> str:
    """
    Valida o tipo de imagem usando magic bytes.
    
    Args:
        binary_data: Dados binários da imagem
        
    Returns:
        Extensão do arquivo (png, jpeg, etc.)
        
    Raises:
        ImageStorageError: Se não for um tipo de imagem válido
    """
    # Verificar magic bytes
    for signature, ext in IMAGE_SIGNATURES.items():
        if binary_data.startswith(signature):
            # Verificação adicional para WebP
            if ext == 'webp' and b'WEBP' not in binary_data[:12]:
                continue
            return ext
    
    raise ImageStorageError(
        "Tipo de arquivo não suportado. Use PNG, JPEG, GIF, BMP ou WebP."
    )


def _validate_image_dimensions(binary_data: bytes, file_ext: str) -> None:
    """
    Valida dimensões da imagem (requer Pillow para validação completa).
    Por enquanto, apenas valida tamanho do arquivo.
    
    Args:
        binary_data: Dados binários da imagem
        file_ext: Extensão do arquivo
        
    Raises:
        ImageStorageError: Se as dimensões forem inválidas
    """
    # Validação básica: se o arquivo for muito pequeno, provavelmente está corrompido
    if len(binary_data) < 100:
        raise ImageStorageError("Arquivo de imagem muito pequeno ou corrompido")
    
    # Validação completa de dimensões requer Pillow (opcional)
    # Por enquanto, apenas logamos um aviso se o arquivo for muito grande
    if len(binary_data) > 3 * 1024 * 1024:  # > 3MB
        logger.warning(
            f"Imagem grande detectada ({len(binary_data) / 1024 / 1024:.2f}MB). "
            "Considere comprimir antes do upload."
        )


def _check_disk_space(required_bytes: int) -> None:
    """
    Verifica se há espaço suficiente em disco.
    
    Args:
        required_bytes: Bytes necessários
        
    Raises:
        ImageStorageError: Se não houver espaço suficiente
    """
    try:
        stat = shutil.disk_usage(MEDIA_ROOT)
        free_space = stat.free
        
        # Requer pelo menos 2x o espaço necessário como margem de segurança
        if free_space < required_bytes * 2:
            raise ImageStorageError(
                f"Espaço em disco insuficiente. "
                f"Necessário: {required_bytes / 1024 / 1024:.2f}MB, "
                f"Disponível: {free_space / 1024 / 1024:.2f}MB"
            )
    except OSError as exc:
        logger.warning(f"Não foi possível verificar espaço em disco: {exc}")
        # Não bloqueia o upload se não conseguir verificar


def delete_ficha_image(relative_path: Optional[str]) -> bool:
    """
    Deleta uma imagem de ficha do sistema de arquivos.
    
    Args:
        relative_path: Caminho relativo da imagem
        
    Returns:
        True se deletou com sucesso, False caso contrário
    """
    if not relative_path:
        return False
    
    try:
        absolute_path = absolute_media_path(relative_path)
        if absolute_path.exists():
            absolute_path.unlink(missing_ok=True)
            logger.info(f"Imagem deletada: {relative_path}")
            return True
    except ImageStorageError:
        logger.warning(f"Tentativa de deletar caminho inválido: {relative_path}")
    except Exception as exc:
        logger.error(f"Erro ao deletar imagem {relative_path}: {exc}")
    
    return False


async def save_base64_image(base64_str: str, ficha_id: int) -> str:
    """
    Salva uma imagem em base64 como arquivo físico.
    Versão robusta com validações de segurança.
    
    Args:
        base64_str: String base64 da imagem (pode ser data URL ou apenas base64)
        ficha_id: ID da ficha para criar a pasta
    
    Returns:
        Caminho relativo da imagem salva: "fichas/{ficha_id}/{uuid}.{ext}"
    
    Raises:
        ImageStorageError: Se houver erro ao decodificar ou salvar
    """
    if not base64_str or not base64_str.strip():
        raise ImageStorageError("String base64 vazia")
    
    # Remover prefixo data URL se existir (data:image/png;base64,...)
    base64_data = base64_str.strip()
    if base64_data.startswith("data:"):
        # Extrair apenas a parte base64
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]
    
    # Decodificar base64
    try:
        binary_data = base64.b64decode(base64_data, validate=True)
    except binascii.Error as exc:
        raise ImageStorageError("Conteúdo base64 inválido") from exc
    
    # Validar tamanho máximo (5MB)
    if len(binary_data) > MAX_IMAGE_SIZE_BYTES:
        raise ImageStorageError(
            f"Imagem excede o limite de 5MB. Tamanho atual: {len(binary_data) / 1024 / 1024:.2f}MB"
        )
    
    # Validar tipo de arquivo usando magic bytes
    try:
        file_ext = _validate_image_type(binary_data)
    except ImageStorageError:
        raise
    except Exception as exc:
        logger.error(f"Erro ao validar tipo de imagem: {exc}")
        raise ImageStorageError("Erro ao validar tipo de arquivo") from exc
    
    # Validar dimensões
    try:
        _validate_image_dimensions(binary_data, file_ext)
    except ImageStorageError:
        raise
    except Exception as exc:
        logger.warning(f"Erro ao validar dimensões: {exc}")
        # Não bloqueia o upload se a validação de dimensões falhar
    
    # Verificar espaço em disco
    try:
        _check_disk_space(len(binary_data))
    except ImageStorageError:
        raise
    except Exception as exc:
        logger.warning(f"Erro ao verificar espaço em disco: {exc}")
        # Não bloqueia o upload se não conseguir verificar
    
    # Criar pasta para a ficha se não existir
    ficha_dir = FICHAS_MEDIA_ROOT / str(ficha_id)
    try:
        ficha_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ImageStorageError(f"Erro ao criar diretório: {exc}") from exc
    
    # Gerar UUID como nome do arquivo com extensão correta
    filename = f"{uuid4().hex}.{file_ext}"
    destination = ficha_dir / filename
    
    # Salvar arquivo de forma assíncrona (compatível com Windows e Linux)
    try:
        import aiofiles
        async with aiofiles.open(destination, "wb") as file_obj:
            await file_obj.write(binary_data)
    except OSError as exc:
        raise ImageStorageError(f"Erro ao salvar arquivo: {exc}") from exc
    except Exception as exc:
        raise ImageStorageError(f"Erro inesperado ao salvar arquivo: {exc}") from exc
    
    # Retornar caminho relativo (usando / para compatibilidade)
    relative_path = destination.relative_to(MEDIA_ROOT)
    path_str = str(relative_path).replace("\\", "/")  # Normalizar para usar /
    
    logger.info(f"Imagem da ficha {ficha_id} salva em {path_str} ({len(binary_data) / 1024:.2f}KB)")
    
    return path_str


def absolute_media_path(relative_path: str) -> Path:
    """
    Retorna o caminho absoluto de um caminho relativo de mídia.
    
    Args:
        relative_path: Caminho relativo (ex: "fichas/1/uuid.png")
    
    Returns:
        Path absoluto do arquivo
    
    Raises:
        ImageStorageError: Se o caminho for inválido
    """
    safe_relative = Path(relative_path)
    absolute = (MEDIA_ROOT / safe_relative).resolve()
    
    # Verificar segurança do caminho (prevenir path traversal)
    try:
        absolute.relative_to(MEDIA_ROOT)
    except ValueError:
        raise ImageStorageError("Caminho de mídia inválido (tentativa de path traversal detectada).")
    
    return absolute

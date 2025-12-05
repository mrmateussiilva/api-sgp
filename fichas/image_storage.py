"""
Utilitário para salvar imagens base64 de fichas.
Compatível com Windows e Linux usando pathlib.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Optional
from uuid import uuid4

from config import settings

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


class ImageStorageError(ValueError):
    """Erro ao processar ou salvar imagem."""


def save_base64_image(base64_str: str, ficha_id: int) -> str:
    """
    Salva uma imagem em base64 como arquivo físico.
    
    Args:
        base64_str: String base64 da imagem (pode ser data URL ou apenas base64)
        ficha_id: ID da ficha para criar a pasta
    
    Returns:
        Caminho relativo da imagem salva: "media/fichas/{ficha_id}/{uuid}.png"
    
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
    
    # Criar pasta para a ficha se não existir
    ficha_dir = FICHAS_MEDIA_ROOT / str(ficha_id)
    ficha_dir.mkdir(parents=True, exist_ok=True)
    
    # Gerar UUID como nome do arquivo
    filename = f"{uuid4().hex}.png"
    destination = ficha_dir / filename
    
    # Salvar arquivo (compatível com Windows e Linux via pathlib)
    try:
        with destination.open("wb") as file_obj:
            file_obj.write(binary_data)
    except Exception as exc:
        raise ImageStorageError(f"Erro ao salvar arquivo: {str(exc)}") from exc
    
    # Retornar caminho relativo (usando / para compatibilidade)
    relative_path = destination.relative_to(MEDIA_ROOT)
    path_str = str(relative_path).replace("\\", "/")  # Normalizar para usar /
    
    print(f"[UPLOAD] Imagem da ficha {ficha_id} salva em {path_str}")
    
    return path_str


def absolute_media_path(relative_path: str) -> Path:
    """
    Retorna o caminho absoluto de um caminho relativo de mídia.
    
    Args:
        relative_path: Caminho relativo (ex: "media/fichas/1/uuid.png")
    
    Returns:
        Path absoluto do arquivo
    
    Raises:
        ImageStorageError: Se o caminho for inválido
    """
    safe_relative = Path(relative_path)
    absolute = (MEDIA_ROOT / safe_relative).resolve()
    
    # Verificar segurança do caminho
    try:
        absolute.relative_to(MEDIA_ROOT)
    except ValueError:
        raise ImageStorageError("Caminho de mídia inválido.")
    
    return absolute


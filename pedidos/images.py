from __future__ import annotations

import base64
import binascii
import mimetypes
import re
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

from config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_configured_media_root = Path(settings.MEDIA_ROOT)
if not _configured_media_root.is_absolute():
    MEDIA_ROOT = (PROJECT_ROOT / _configured_media_root).resolve()
else:
    MEDIA_ROOT = _configured_media_root.resolve()

PEDIDOS_MEDIA_ROOT = MEDIA_ROOT / "pedidos"
PEDIDOS_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_SIZE_BYTES = max(settings.MAX_IMAGE_SIZE_MB, 1) * 1024 * 1024

DATA_URL_PATTERN = re.compile(
    r"^data:(?P<mime>[\w.+/-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$"
)


class ImageDecodingError(ValueError):
    """Erro ao interpretar os dados de imagem enviados."""


def is_data_url(value: Optional[str]) -> bool:
    return bool(value and DATA_URL_PATTERN.match(value.strip()))


def decode_base64_image(data_url: str) -> Tuple[bytes, str]:
    match = DATA_URL_PATTERN.match((data_url or "").strip())
    if not match:
        raise ImageDecodingError("Formato de imagem inválido. Use data URL base64.")

    mime_type = match.group("mime") or "application/octet-stream"
    data_part = "".join(match.group("data").split())
    try:
        binary_data = base64.b64decode(data_part, validate=True)
    except binascii.Error as exc:
        raise ImageDecodingError("Conteúdo base64 inválido.") from exc

    if len(binary_data) > MAX_IMAGE_SIZE_BYTES:
        raise ImageDecodingError(
            f"Imagem excede o limite de {settings.MAX_IMAGE_SIZE_MB}MB."
        )

    return binary_data, mime_type


def _pedido_media_dir(pedido_id: Optional[int]) -> Path:
    if not pedido_id:
        path = PEDIDOS_MEDIA_ROOT / "tmp"
    else:
        path = PEDIDOS_MEDIA_ROOT / str(pedido_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _extension_for(mime_type: str, original_name: Optional[str] = None) -> str:
    if original_name:
        name = Path(original_name)
        if name.suffix:
            return name.suffix

    guessed = mimetypes.guess_extension(mime_type or "")
    if not guessed:
        return ".bin"

    if guessed == ".jpe":
        return ".jpg"
    return guessed


def store_image_bytes(
    pedido_id: int,
    data: bytes,
    mime_type: str,
    original_filename: Optional[str] = None,
) -> Tuple[str, str, int]:
    target_dir = _pedido_media_dir(pedido_id)
    extension = _extension_for(mime_type, original_filename)
    filename = f"{uuid4().hex}{extension}"
    destination = target_dir / filename
    with destination.open("wb") as file_obj:
        file_obj.write(data)

    relative_path = destination.relative_to(MEDIA_ROOT)
    return str(relative_path), filename, len(data)


def absolute_media_path(relative_path: str) -> Path:
    safe_relative = Path(relative_path)
    absolute = (MEDIA_ROOT / safe_relative).resolve()
    if MEDIA_ROOT not in absolute.parents and absolute != MEDIA_ROOT:
        raise ImageDecodingError("Caminho de mídia inválido.")
    return absolute


def delete_media_file(relative_path: Optional[str]) -> None:
    if not relative_path:
        return
    try:
        target = absolute_media_path(relative_path)
    except ImageDecodingError:
        return
    if target.exists():
        target.unlink(missing_ok=True)

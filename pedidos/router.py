from dataclasses import dataclass
from typing import Any, List, Optional
import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File, Form, BackgroundTasks
from sqlmodel import select, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text, func, case
from sqlalchemy.exc import IntegrityError, OperationalError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from typing import Any
from base import get_session
from database.database import engine
from .schema import (
    Pedido,
    PedidoCreate,
    PedidoUpdate,
    PedidoResponse,
    ItemPedido,
    Acabamento,
    Status,
    PedidoImagem,
    BatchStatusUpdate,
)
from .realtime import schedule_broadcast
from datetime import datetime, timedelta, timezone
import orjson
from auth.security import decode_access_token
from auth.models import User
from fastapi.security import OAuth2PasswordBearer
from config import settings
from .images import (
    decode_base64_image,
    delete_media_file,
    is_data_url,
    store_image_bytes,
    absolute_media_path,
    ImageDecodingError,
    MEDIA_ROOT,
    PEDIDOS_MEDIA_ROOT,
)
from .service import (
    normalize_acabamento,
    item_to_plain_dict,
    items_to_json_string,
    json_string_to_items,
    normalize_pedido_status,
    decode_city_state,
    encode_city_state,
    pedido_to_response_dict,
    _save_pedido_json_internal,
)
from .pricing import normalize_order_financials
import aiofiles
from pathlib import Path
from uuid import uuid4
import mimetypes
from shared.vps_sync_service import vps_sync_service
from sync.schema import SyncEntity, SyncEventType
from sync.service import enqueue_sync_event
from materiais.stock_service import (
    apply_material_stock_delta,
    build_material_stock_delta,
    is_stock_eligible_status,
    summarize_material_consumption,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="ignored", auto_error=False)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

# Variável global para rastrear o último ID de pedido criado
# Usada pelo sistema de notificações para long polling
ULTIMO_PEDIDO_ID = 0

STATE_SEPARATOR = "||"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100000  # Limite muito alto para permitir buscar todos os pedidos


def is_material_stock_enabled() -> bool:
    return bool(getattr(settings, "MATERIAL_STOCK_AUTO_DEDUCTION", False))


@dataclass
class PendingImageUpload:
    index: int
    identifier: Optional[str]
    data_url: str


@dataclass
class PendingImageRemoval:
    index: int
    identifier: Optional[str]


async def get_current_user_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
) -> bool:
    """
    Verifica se o usuário atual é administrador a partir do token JWT.
    Tokens ausentes ou inválidos retornam False.
    """
    if not token:
        return False

    payload = decode_access_token(token)
    if not payload:
        return False

    user_id: Optional[int] = payload.get("user_id")
    if not user_id:
        return False

    user = await session.get(User, user_id)
    if not user or not user.is_active:
        return False

    return bool(user.is_admin)


async def require_admin(
    is_admin: bool = Depends(get_current_user_admin)
) -> bool:
    """
    Dependência que garante que o usuário é administrador.
    Retorna HTTP 403 se não for admin.
    """
    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Ação permitida apenas para administradores."
        )
    return True


async def get_current_user_from_token(token: Optional[str], session: AsyncSession) -> Optional[dict[str, Any]]:
    """Extrai informações do usuário atual do token JWT"""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("user_id")
    username = payload.get("sub")
    if not user_id:
        return None
    # Buscar usuário no banco para obter username completo
    user = await session.get(User, user_id)
    if user:
        return {"user_id": user.id, "username": user.username}
    return {"user_id": user_id, "username": username or f"User {user_id}"}


def broadcast_order_event(event_type: str, pedido: Optional[PedidoResponse] = None, order_id: Optional[int] = None, user_info: Optional[dict[str, Any]] = None) -> None:
    message: dict[str, Any] = {"type": event_type}
    if pedido is not None:
        pedido_dict = jsonable_encoder(pedido)
        # Adicionar informações do usuário ao pedido se disponível
        if user_info:
            pedido_dict["user_id"] = user_info.get("user_id")
            pedido_dict["username"] = user_info.get("username")
        message["order"] = pedido_dict
        # Garantir que order_id está na mensagem também
        if pedido_dict.get("id"):
            message["order_id"] = pedido_dict["id"]
    if order_id is not None:
        message["order_id"] = order_id
    # Adicionar informações do usuário na mensagem também
    if user_info:
        message["user_id"] = user_info.get("user_id")
        message["username"] = user_info.get("username")
    
    # Log detalhado para debug
    if __debug__:
        print(f"[Broadcast] Preparando broadcast: type={event_type}, order_id={message.get('order_id')}, user_id={message.get('user_id')}, username={message.get('username')}")
        print(f"[Broadcast] Mensagem completa: {message}")
    
    schedule_broadcast(message)

# _save_pedido_json_internal moved to service.py

def build_api_path(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    prefix = (settings.API_V1_STR or "").strip()
    if not prefix:
        return normalized
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return f"{prefix.rstrip('/')}{normalized}"

# helper functions moved to service.py:
# normalize_acabamento
# item_to_plain_dict
# items_to_json_string
# json_string_to_items
# normalize_pedido_status
# pedido_to_response_dict

def resolve_item_identifier(item_dict: dict[str, Any]) -> Optional[str]:
    identifier = item_dict.get('id')
    if identifier is None:
        return None
    return str(identifier)


def prepare_items_for_storage(
    items_payload,
    allow_removal: bool = False
) -> tuple[list[dict[str, Any]], list[PendingImageUpload], list[PendingImageRemoval]]:
    normalized_items: list[dict[str, Any]] = []
    pending_uploads: list[PendingImageUpload] = []
    pending_removals: list[PendingImageRemoval] = []

    for index, item in enumerate(items_payload):
        item_dict = item_to_plain_dict(item)
        identifier = resolve_item_identifier(item_dict)
        if 'imagem' in item_dict:
            image_value = item_dict.get('imagem')
            if isinstance(image_value, str) and is_data_url(image_value):
                pending_uploads.append(PendingImageUpload(index, identifier, image_value))
                item_dict['imagem'] = None
                item_dict['imagem_path'] = None
            elif (
                allow_removal
                and identifier
                and (image_value is None or (isinstance(image_value, str) and not image_value.strip()))
            ):
                pending_removals.append(PendingImageRemoval(index, identifier))
                item_dict['imagem'] = None
                item_dict['imagem_path'] = None
        normalized_items.append(item_dict)
    return normalized_items, pending_uploads, pending_removals


def _matches_image_record(image: PedidoImagem, identifier: Optional[str], index: int) -> bool:
    if identifier and image.item_identificador:
        return image.item_identificador == identifier
    return image.item_index == index


async def apply_image_changes(
    session: AsyncSession,
    pedido_id: int,
    uploads: List[PendingImageUpload],
    removals: List[PendingImageRemoval],
    items_payload: List[dict[str, Any]],
) -> bool:
    # Também precisamos tratar referências já existentes apontando para pedidos/tmp/*
    # (imagem selecionada previamente e salva como path relativo), promovendo para
    # pedidos/{pedido_id}/ e criando registro PedidoImagem.
    promotions: list[tuple[int, Optional[str], str]] = []
    for index, item in enumerate(items_payload):
        image_value = item.get("imagem")
        if not isinstance(image_value, str):
            continue
        normalized = image_value.strip().lstrip("/")
        if normalized.startswith("pedidos/tmp/"):
            promotions.append((index, resolve_item_identifier(item), normalized))

    if not uploads and not removals and not promotions:
        return False

    result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido_id))
    existing_images = result.all()

    identifier_to_index = {}
    for index, item in enumerate(items_payload):
        identifier = resolve_item_identifier(item)
        if identifier:
            identifier_to_index[identifier] = index

    for image in existing_images:
        if image.item_identificador and image.item_identificador in identifier_to_index:
            new_index = identifier_to_index[image.item_identificador]
            if image.item_index != new_index:
                image.item_index = new_index
                session.add(image)

    async def _remove_image(record: PedidoImagem) -> None:
        await delete_media_file(record.path)
        await session.delete(record)

    def _pop_matching(identifier: Optional[str], index: int) -> Optional[PedidoImagem]:
        for existing in list(existing_images):
            if _matches_image_record(existing, identifier, index):
                existing_images.remove(existing)
                return existing
        return None

    has_changes = False

    for removal in removals:
        record = _pop_matching(removal.identifier, removal.index)
        if record:
            await _remove_image(record)
            has_changes = True
            if 0 <= removal.index < len(items_payload):
                items_payload[removal.index]['imagem'] = None
                items_payload[removal.index]['imagem_path'] = None

    for upload in uploads:
        record = _pop_matching(upload.identifier, upload.index)
        if record:
            await _remove_image(record)
        try:
            binary_data, mime_type = decode_base64_image(upload.data_url)
        except ImageDecodingError as exc:
            logger.error("Erro ao decodificar imagem: %s", exc)
            raise HTTPException(status_code=400, detail="Erro ao processar imagem") from exc

        relative_path, filename, size = await store_image_bytes(
            pedido_id,
            binary_data,
            mime_type,
        )
        image_row = PedidoImagem(
            pedido_id=pedido_id,
            item_index=upload.index,
            item_identificador=upload.identifier,
            filename=filename,
            mime_type=mime_type,
            path=relative_path,
            tamanho=size,
        )
        session.add(image_row)
        await session.flush()
        url = build_api_path(f"/pedidos/imagens/{image_row.id}")
        print(f"[UPLOAD] URL da imagem construída: {url} para item index {upload.index}")
        if 0 <= upload.index < len(items_payload):
            items_payload[upload.index]['imagem'] = url
            items_payload[upload.index]['imagem_path'] = str(relative_path)
            print(f"[UPLOAD] Caminho da imagem salvo no item: {items_payload[upload.index].get('imagem')}")
        has_changes = True


    # Promover imagens que ficaram como referência em pedidos/tmp/*
    # Isso evita que a imagem "suma" ao editar (tmp pode ser limpo ou não estar vinculado ao pedido).
    for index, identifier, tmp_rel in promotions:
        record = _pop_matching(identifier, index)
        if record:
            await _remove_image(record)

        try:
            src = absolute_media_path(tmp_rel)
            async with aiofiles.open(src, "rb") as f:
                binary_data = await f.read()

            mime_type = mimetypes.guess_type(src.name)[0] or "image/jpeg"
            relative_path, filename, size = await store_image_bytes(
                pedido_id,
                binary_data,
                mime_type,
                original_filename=src.name,
            )

            image_row = PedidoImagem(
                pedido_id=pedido_id,
                item_index=index,
                item_identificador=identifier,
                filename=filename,
                mime_type=mime_type,
                path=relative_path,
                tamanho=size,
            )
            session.add(image_row)
            await session.flush()

            url = build_api_path(f"/pedidos/imagens/{image_row.id}")
            if 0 <= index < len(items_payload):
                items_payload[index]["imagem"] = url
                items_payload[index]["imagem_path"] = str(relative_path)

            # Apagar tmp antigo (best-effort)
            await delete_media_file(tmp_rel)

            has_changes = True
        except Exception as e:
            print(f"[PROMOTE-TMP] Erro ao promover imagem {tmp_rel}: {e}")
    return has_changes


async def populate_items_with_image_paths(
    session: AsyncSession,
    pedido_id: int,
    items: List[ItemPedido],
) -> None:
    """Popula items com caminhos de imagens para um único pedido."""
    if not items:
        return

    result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido_id))
    images = result.all()
    if not images:
        return

    def _item_identifier(item: ItemPedido) -> Optional[str]:
        value = getattr(item, 'id', None)
        if value is None:
            return None
        return str(value)

    for image in images:
        target_item: Optional[ItemPedido] = None
        if image.item_identificador:
            for candidate in items:
                if _item_identifier(candidate) == image.item_identificador:
                    target_item = candidate
                    break
        if target_item is None and image.item_index is not None:
            if 0 <= image.item_index < len(items):
                target_item = items[image.item_index]
        if target_item is None:
            continue

        if not getattr(target_item, 'imagem', None):
            target_item.imagem = build_api_path(f"/pedidos/imagens/{image.id}")
        target_item.imagem_path = image.path


async def populate_items_with_image_paths_batch(
    session: AsyncSession,
    pedidos: List[Pedido],
    pedidos_items: dict[int, List[ItemPedido]],
) -> None:
    """
    Versão otimizada que busca todas as imagens de uma vez (evita N+1 queries).
    Popula items com caminhos de imagens para múltiplos pedidos.
    """
    if not pedidos:
        return
    
    pedido_ids = [p.id for p in pedidos if p.id is not None]
    if not pedido_ids:
        return

    # Uma única query para buscar todas as imagens de todos os pedidos
    result = await session.exec(
        select(PedidoImagem).where(PedidoImagem.pedido_id.in_(pedido_ids))
    )
    all_images = result.all()
    
    # Agrupar imagens por pedido_id
    images_by_pedido: dict[int, List[PedidoImagem]] = {}
    for image in all_images:
        if image.pedido_id not in images_by_pedido:
            images_by_pedido[image.pedido_id] = []
        images_by_pedido[image.pedido_id].append(image)
    
    # Processar imagens para cada pedido
    for pedido_id, items in pedidos_items.items():
        images = images_by_pedido.get(pedido_id, [])
        if not images:
            continue
        
        def _item_identifier(item: ItemPedido) -> Optional[str]:
            value = getattr(item, 'id', None)
            if value is None:
                return None
            return str(value)
        
        for image in images:
            target_item: Optional[ItemPedido] = None
            if image.item_identificador:
                for candidate in items:
                    if _item_identifier(candidate) == image.item_identificador:
                        target_item = candidate
                        break
            if target_item is None and image.item_index is not None:
                if 0 <= image.item_index < len(items):
                    target_item = items[image.item_index]
            if target_item is None:
                continue
            
            if not getattr(target_item, 'imagem', None):
                target_item.imagem = build_api_path(f"/pedidos/imagens/{image.id}")
            target_item.imagem_path = image.path


async def get_next_order_number(session: AsyncSession) -> str:
    """
    Gera o próximo número incremental de pedido baseado no maior número existente.

    A unicidade final é garantida por um índice UNIQUE na coluna numero.
    Se duas requisições concorrentes gerarem o mesmo número, o banco levantará
    IntegrityError e a criação será re-tentada em criar_pedido.
    """
    try:
        result = await session.execute(
            text(
                """
                SELECT MAX(CAST(numero AS INTEGER)) 
                FROM pedidos 
                WHERE numero IS NOT NULL 
                  AND numero != '' 
                  AND CAST(numero AS INTEGER) > 0
                """
            )
        )
        max_num = result.scalar()

        if max_num is None:
            next_num = 1
        else:
            next_num = int(max_num) + 1

        return str(next_num).zfill(10)
    except (ValueError, TypeError) as exc:
        # Números com formato inválido – usar ID como fallback
        logger.warning("[pedidos] Erro ao converter numero, usando ID como fallback: %s", exc)
    except Exception as exc:
        # Outros erros inesperados – usar ID como fallback
        logger.error("[pedidos] Erro inesperado ao gerar numero incremental: %s", exc)

    # Fallback: usar maior id
    try:
        result = await session.execute(text("SELECT MAX(id) FROM pedidos"))
        max_id = result.scalar()
        next_num = (max_id or 0) + 1
        return str(next_num).zfill(10)
    except Exception as exc:
        logger.error("[pedidos] Erro ao usar ID como fallback para numero: %s", exc)
        return "0000000001"


def ensure_pedido_defaults(pedido_data: dict) -> dict:
    """Garante campos obrigatórios com valores padrão."""
    # Nota: numero será gerado assincronamente em criar_pedido
    # Este método apenas preserva o numero se já existir
    numero = pedido_data.get('numero')
    if numero:
        pedido_data['numero'] = numero
    # Se não houver numero, será gerado em criar_pedido usando get_next_order_number

    data_entrada = pedido_data.get('data_entrada') or datetime.utcnow().date().isoformat()
    pedido_data['data_entrada'] = data_entrada

    data_entrega = pedido_data.get('data_entrega') or data_entrada
    pedido_data['data_entrega'] = data_entrega

    forma_envio_id = pedido_data.get('forma_envio_id')
    if forma_envio_id is None or forma_envio_id == '':
        forma_envio_id = 0
    pedido_data['forma_envio_id'] = int(forma_envio_id)

    pedido_data.setdefault('valor_total', '0.00')
    pedido_data.setdefault('valor_itens', '0.00')
    pedido_data.setdefault('valor_frete', '0.00')
    pedido_data.setdefault('tipo_pagamento', '')
    pedido_data.setdefault('cliente', '')
    pedido_data.setdefault('telefone_cliente', '')

    cidade = pedido_data.get('cidade_cliente') or ''
    estado = (pedido_data.pop('estado_cliente', None) or '').strip()
    pedido_data['cidade_cliente'] = encode_city_state(cidade, estado)

    return pedido_data

# encode_city_state e decode_city_state moved to service.py (but encode_city_state needed here too if not imported)
# wait, decode_city_state was moved, but what about encode_city_state?
# encode_city_state wasn't in the list of moved functions in previous thought, checking service.py content...
# Ah, I added encode_city_state to service.py in my thought but I need to check if I actually wrote it there.
# Let me check service.py again briefly or just import it.

@router.get("/imagens/{imagem_id}")
async def obter_imagem(imagem_id: int, session: AsyncSession = Depends(get_session)):
    imagem = await session.get(PedidoImagem, imagem_id)
    if not imagem:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    try:
        absolute_path = absolute_media_path(imagem.path)
    except ImageDecodingError:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(
        absolute_path,
        media_type=imagem.mime_type,
        filename=imagem.filename,
    )


@router.get("/media/{file_path:path}")
async def servir_arquivo_media(file_path: str):
    """
    Serve arquivos do diretório media.
    Permite acesso a imagens salvas em pedidos/tmp/ ou pedidos/{id}/
    Exemplo: /pedidos/media/pedidos/tmp/xxx.jpg
    """
    try:
        absolute_path = absolute_media_path(file_path)
    except ImageDecodingError:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Determinar content-type baseado na extensão
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(absolute_path))
    if not mime_type:
        mime_type = "application/octet-stream"
    
    return FileResponse(
        absolute_path,
        media_type=mime_type,
        filename=absolute_path.name,
    )


@router.post("/order-items/upload-image")
async def upload_image_item(
    image: UploadFile = File(...),
    order_item_id: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint para upload de imagem de item de pedido.
    Aceita FormData com arquivo de imagem e order_item_id opcional.
    
    Se order_item_id for fornecido, associa a imagem ao item existente.
    Caso contrário, salva a imagem em diretório temporário para uso futuro.
    
    Retorna a referência do arquivo (caminho relativo) que pode ser usado
    no campo 'imagem' do item do pedido.
    """
    try:
        # Ler bytes do arquivo
        image_data = await image.read()
        
        if not image_data:
            raise HTTPException(status_code=400, detail="Arquivo vazio")
        
        # Determinar mime_type
        mime_type = image.content_type or "image/jpeg"
        if not mime_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem")
        
        # Se tiver order_item_id, buscar o pedido_id do item
        # (Nota: items estão em JSON, então isso pode não funcionar perfeitamente)
        pedido_id = None
        item_index = None
        
        if order_item_id:
            # Tentar buscar pedido que contém o item com esse ID
            # Como os itens estão em JSON, isso é mais complexo
            # Por enquanto, salvar em diretório temporário
            pedido_id = None
        else:
            # Upload antes de criar pedido - usar diretório temporário
            pedido_id = None
        
        # Salvar imagem (usar diretório temporário se pedido_id for None)
        if pedido_id:
            relative_path, filename, size = await store_image_bytes(
                pedido_id,
                image_data,
                mime_type,
                image.filename,
            )
        else:
            # Salvar em diretório temporário (pedidos/tmp)
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
            
            target_dir = PEDIDOS_MEDIA_ROOT / "tmp"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            extension = _extension_for(mime_type, image.filename)
            filename = f"{uuid4().hex}{extension}"
            destination = target_dir / filename
            
            async with aiofiles.open(destination, "wb") as file_obj:
                await file_obj.write(image_data)
            
            relative_path = destination.relative_to(MEDIA_ROOT)
            size = len(image_data)
        
        # Retornar referência (caminho relativo)
        # O frontend pode usar esse caminho diretamente ou converter para URL
        reference = str(relative_path).replace("\\", "/")
        
        logger.info(
            "Imagem de item enviada: reference=%s, order_item_id=%s, size=%s",
            reference,
            order_item_id,
            size,
        )
        
        # Retornar referência que pode ser usada no campo imagem do item
        # O frontend espera server_reference (ver imageUploader.ts linha 61)
        # A referência é um caminho relativo que será salvo no banco
        return {
            "success": True,
            "server_reference": reference,
            "image_reference": reference,  # Mantido para compatibilidade
            "path": reference,  # Mantido para compatibilidade
            "filename": filename,
            "size": size,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao fazer upload de imagem de item: %s", e)
        raise HTTPException(status_code=500, detail="Erro interno ao processar upload de imagem")

@router.post("/save-json/{pedido_id}")
async def salvar_pedido_json(
    pedido_id: int,
    pedido_data: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Salva os dados completos de um pedido em arquivo JSON.
    O arquivo é salvo em: api-sgp/media/pedidos/{pedido_id}/
    """
    try:
        # Re-use internal function
        await _save_pedido_json_internal(pedido_id, pedido_data)
        
        return {
            "message": "JSON salvo com sucesso",
            "pedido_id": pedido_id
        }
        
    except Exception as e:
        logger.exception("Erro ao salvar JSON do pedido %s", pedido_id)
        raise HTTPException(status_code=500, detail="Erro interno ao salvar JSON do pedido")


@router.get("/{pedido_id}/json")
async def obter_pedido_json(
    pedido_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Busca o arquivo JSON mais recente de um pedido.
    Retorna o JSON completo com todos os dados do pedido.
    """
    try:
        from pathlib import Path
        import json
        import aiofiles
        
        # Obter caminho do projeto (mesmo padrão usado em save-json)
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        from config import settings
        _configured_media_root = Path(settings.MEDIA_ROOT)
        if not _configured_media_root.is_absolute():
            MEDIA_ROOT = (PROJECT_ROOT / _configured_media_root).resolve()
        else:
            MEDIA_ROOT = _configured_media_root.resolve()
        
        # Diretório do pedido
        pedido_dir = MEDIA_ROOT / "pedidos" / str(pedido_id)
        
        if not pedido_dir.exists():
            raise HTTPException(status_code=404, detail=f"JSON do pedido {pedido_id} não encontrado")
        
        # Buscar o arquivo JSON mais recente
        json_files = list(pedido_dir.glob("pedido-*.json"))
        if not json_files:
            raise HTTPException(status_code=404, detail=f"JSON do pedido {pedido_id} não encontrado")
        
        # Ordenar por data de modificação (mais recente primeiro)
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_json = json_files[0]
        
        # Ler e retornar o JSON
        async with aiofiles.open(latest_json, 'r', encoding='utf-8') as f:
            content = await f.read()
            json_data = json.loads(content)
        
        # Remover metadados internos antes de retornar
        json_data.pop('savedAt', None)
        json_data.pop('savedBy', None)
        json_data.pop('version', None)
        
        return json_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao buscar JSON do pedido %s", pedido_id)
        raise HTTPException(status_code=500, detail="Erro interno ao buscar JSON do pedido")


@router.post("/", response_model=PedidoResponse)
async def criar_pedido(
    pedido: PedidoCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Cria um novo pedido com todos os dados fornecidos.
    Aceita o JSON completo com items, dados do cliente, valores, etc.

    Resistente a concorrência:
    - numero é protegido por UNIQUE em banco;
    - em caso de colisão ou pequenos locks, há tentativas extras antes de falhar.
    """
    MAX_RETRIES = 5

    # Converter o pedido para dict e preparar base para reuso entre tentativas
    base_pedido_data = pedido.model_dump(exclude_unset=True)
    raw_items = base_pedido_data.pop("items", [])
    items_payload, pending_uploads, _ = prepare_items_for_storage(raw_items)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pedido_data = dict(base_pedido_data)
            pedido_data = ensure_pedido_defaults(pedido_data)

            if not pedido_data.get("numero"):
                pedido_data["numero"] = await get_next_order_number(session)

            if is_material_stock_enabled() and is_stock_eligible_status(pedido_data.get("status")):
                consumo_novo = summarize_material_consumption(items_payload)
                await apply_material_stock_delta(session, consumo_novo)

            # ── Recalcular valor_unitario e totais do pedido no backend ──────────
            # Guardrail: recalcula items e totais independentemente do frontend.
            items_payload, totais = normalize_order_financials(
                items_payload, 
                pedido_data.get("valor_frete")
            )
            pedido_data["valor_itens"] = totais["valor_itens"]
            pedido_data["valor_total"] = totais["valor_total"]
            # ─────────────────────────────────────────────────────────────────────

            items_json = items_to_json_string(items_payload)

            db_pedido = Pedido(
                **pedido_data,
                items=items_json,
                data_criacao=datetime.utcnow(),
                ultima_atualizacao=datetime.utcnow(),
            )

            session.add(db_pedido)
            await session.flush()
            pedido_id_snapshot = db_pedido.id

            if await apply_image_changes(session, db_pedido.id, pending_uploads, [], items_payload):
                db_pedido.items = items_to_json_string(items_payload)

            await enqueue_sync_event(
                session,
                entity=SyncEntity.PEDIDO.value,
                event_type=SyncEventType.UPSERT.value,
                entity_id=db_pedido.id,
                payload={"pedido_id": db_pedido.id},
            )
            await session.commit()
            
            # Registrar logs de produção para itens com máquina atribuída
            try:
                from maquinas.print_log_schema import PrintLog, PrintLogStatus
                for item_idx, item in enumerate(items_payload):
                    m_id = item.get("machine_id")
                    if m_id and isinstance(m_id, (int, str)):
                        try:
                            m_id_int = int(m_id)
                            if m_id_int > 0:
                                # Tenta pegar o ID do item se ele já existir (o que não deve ser o caso aqui em um novo pedido, 
                                # mas o prepare_items_for_storage pode ter populado algo se vier de um clone/sync)
                                item_id_val = item.get("id")
                                # Se não tem item_id, usamos um fallback baseado no pedido_id * 1000 + index
                                if not item_id_val:
                                    item_id_val = db_pedido.id * 1000 + item_idx

                                print_log = PrintLog(
                                    printer_id=m_id_int,
                                    pedido_id=db_pedido.id,
                                    item_id=item_id_val,
                                    status=PrintLogStatus.SUCCESS
                                )
                                session.add(print_log)
                        except (ValueError, TypeError):
                            continue
                await session.commit()
            except Exception as log_error:
                logger.warning(f"Erro ao criar logs iniciais de produção: {log_error}")
            # Em testes de concorrência com SQLite+aiosqlite, refresh pode falhar de forma espúria.
            if settings.ENVIRONMENT != "test":
                try:
                    await session.refresh(db_pedido)
                except Exception as e:
                    logger.warning(
                        "Falha ao dar refresh no pedido %s após commit (concorrência): %s",
                        pedido_id_snapshot,
                        e,
                    )

            pedido_dict = db_pedido.model_dump()
            cidade, estado = decode_city_state(pedido_dict.get("cidade_cliente"))
            pedido_dict["cidade_cliente"] = cidade
            pedido_dict["estado_cliente"] = estado
            items_response = json_string_to_items(db_pedido.items or "[]")
            await populate_items_with_image_paths(session, db_pedido.id, items_response)
            pedido_dict["items"] = items_response
            response = PedidoResponse(**pedido_dict)

            user_info = await get_current_user_from_token(token, session)
            logger.info(
                "Pedido criado com sucesso id=%s numero=%s cliente=%s",
                db_pedido.id,
                db_pedido.numero,
                db_pedido.cliente,
            )
            
            # Atualizar o último ID de pedido para o sistema de notificações
            global ULTIMO_PEDIDO_ID
            if db_pedido.id is not None:
                ULTIMO_PEDIDO_ID = db_pedido.id
            
            # 🔥 Garantir JSON atualizado ANTES do broadcast (evita /json stale nos clientes)

            
            await _save_pedido_json_internal(db_pedido.id, jsonable_encoder(response))

            
            broadcast_order_event("order_created", response, None, user_info)
            
            # Sincronizar com a VPS (Background)
            background_tasks.add_task(vps_sync_service.sync_pedido, response)

            return response

        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as exc:
            await session.rollback()
            msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
            if "uq_pedidos_numero" in msg or "unique" in msg or "numero" in msg:
                if attempt >= MAX_RETRIES:
                    logger.error(
                        "Falha ao gerar numero único para pedido após %s tentativas: %s",
                        attempt,
                        exc,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail="Não foi possível gerar número único para o pedido. Tente novamente.",
                    ) from exc
                logger.warning("Colisão de numero de pedido detectada, tentando novamente (tentativa %s)", attempt)
                await asyncio.sleep(0.1 * attempt)  # Backoff exponencial: 0.1s, 0.2s, 0.3s, 0.4s, 0.5s
                continue
            logger.error("Erro de integridade ao criar pedido: %s", exc)
            raise HTTPException(status_code=400, detail="Erro de integridade ao criar pedido") from exc
        except OperationalError as exc:
            await session.rollback()
            msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
            if "database is locked" in msg:
                if attempt >= MAX_RETRIES:
                    logger.error("Banco de dados locked ao criar pedido após %s tentativas: %s", attempt, exc)
                    raise HTTPException(
                        status_code=503,
                        detail="Banco de dados temporariamente ocupado. Tente novamente em instantes.",
                    ) from exc
                logger.warning("database is locked ao criar pedido, tentando novamente (tentativa %s)", attempt)
                await asyncio.sleep(0.1 * attempt)  # Backoff exponencial: 0.1s, 0.2s, 0.3s, 0.4s, 0.5s
                continue
            logger.error("Erro de banco ao criar pedido: %s", exc)
            raise HTTPException(status_code=400, detail="Erro interno ao processar pedido") from exc
        except Exception as exc:
            await session.rollback()
            logger.exception("Erro inesperado ao criar pedido: %s", exc)
            raise HTTPException(status_code=400, detail="Erro interno ao criar pedido") from exc

def _validate_iso_date(value: Optional[str], field_name: str) -> Optional[str]:
    if not value:
        return None
    try:
        # Aceitar tanto formato YYYY-MM-DD quanto formato ISO completo
        value = value.strip()
        if len(value) == 10 and value.count('-') == 2:
            # Formato YYYY-MM-DD - validar e retornar como está
            datetime.strptime(value, "%Y-%m-%d")
            return value
        else:
            # Formato ISO completo - validar e extrair apenas a data
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError) as e:
        raise HTTPException(status_code=400, detail=f"{field_name} inválida: {value}. Use o formato YYYY-MM-DD.")


@router.get("/", response_model=List[PedidoResponse])
async def listar_pedidos(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    status: Optional[Status] = Query(default=None),
    cliente: Optional[str] = Query(default=None),
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada', 'entrega' ou 'qualquer'"),
):
    """
    Lista todos os pedidos com seus items convertidos de volta para objetos. 
    
    Parâmetros:
    - date_mode: Define qual campo de data usar para filtro:
      * 'entrada': Filtra por data_entrada
      * 'entrega': Filtra por data_entrega
      * 'qualquer': Filtra por qualquer uma das duas datas (data_entrada OU data_entrega)
    """
    try:
        filters = select(Pedido)
        if status:
            filters = filters.where(Pedido.status == status)

        if cliente:
            # Normalizar cliente para busca (remover acentos e caracteres especiais)
            import unicodedata
            cliente_normalized = unicodedata.normalize('NFKD', cliente.strip().lower())
            cliente_normalized = ''.join(c for c in cliente_normalized if not unicodedata.combining(c))
            search = f"%{cliente_normalized}%"
            
            # Usar função REPLACE do SQLite para normalizar também a coluna cliente
            # Substituir caracteres acentuados comuns: Ç->c, Á->a, É->e, Í->i, Ó->o, Ú->u, Ã->a, Õ->o
            cliente_col_normalized = func.lower(Pedido.cliente)
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ç', 'c')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'á', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'à', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ã', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'â', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'é', 'e')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ê', 'e')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'í', 'i')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ó', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ô', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'õ', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ú', 'u')
            
            filters = filters.where(cliente_col_normalized.like(search))
            logger.info(f"[listar_pedidos] Filtro cliente aplicado (normalizado): {search}")

        data_inicio = _validate_iso_date(data_inicio, "data_inicio")
        data_fim = _validate_iso_date(data_fim, "data_fim")

        if data_inicio and data_fim and data_inicio > data_fim:
            raise HTTPException(status_code=400, detail="data_inicio deve ser menor ou igual a data_fim")

        # Aplicar filtro de data conforme date_mode
        if data_inicio or data_fim:
            date_mode_normalized = (date_mode or "entrega").lower().strip()
            
            if date_mode_normalized == "entrada":
                if data_inicio:
                    filters = filters.where(Pedido.data_entrada >= data_inicio)
                if data_fim:
                    next_day = (datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    filters = filters.where(Pedido.data_entrada < next_day)
            
            elif date_mode_normalized == "qualquer":
                if data_inicio and data_fim:
                    next_day = (datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    filters = filters.where(
                        or_(
                            and_(Pedido.data_entrada >= data_inicio, Pedido.data_entrada < next_day),
                            and_(Pedido.data_entrega >= data_inicio, Pedido.data_entrega < next_day)
                        )
                    )
                elif data_inicio:
                    filters = filters.where(
                        or_(Pedido.data_entrada >= data_inicio, Pedido.data_entrega >= data_inicio)
                    )
                elif data_fim:
                    next_day = (datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    filters = filters.where(
                        or_(Pedido.data_entrada < next_day, Pedido.data_entrega < next_day)
                    )
            
            else:
                # Padrão: filtrar por data_entrega
                if data_inicio:
                    filters = filters.where(Pedido.data_entrega >= data_inicio)
                if data_fim:
                    next_day = (datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    filters = filters.where(Pedido.data_entrega < next_day)
        
        filters = filters.order_by(Pedido.data_criacao.desc()).offset(skip)
        if limit is not None:
            filters = filters.limit(limit)
        
        # Log da query para debug
        logger.info(f"[listar_pedidos] Executando query com filtros: skip={skip}, limit={limit}, status={status}, cliente={cliente}, data_inicio={data_inicio}, data_fim={data_fim}, date_mode={date_mode}")
        
        # DEBUG: Testar query SQL direta primeiro
        if cliente and (data_inicio or data_fim):
            logger.info(f"[listar_pedidos] 🔍 DEBUG: Testando query SQL direta...")
            
            fim_date = datetime.strptime(data_fim, "%Y-%m-%d")
            fim_plus_one = (fim_date + timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Normalizar cliente para busca (remover acentos)
            import unicodedata
            cliente_normalized = unicodedata.normalize('NFKD', cliente.strip().lower())
            cliente_normalized = ''.join(c for c in cliente_normalized if not unicodedata.combining(c))
            cliente_pattern = f"%{cliente_normalized}%"
            
            logger.info(f"[listar_pedidos] 🔍 DEBUG Parâmetros: cliente_pattern={cliente_pattern}, data_inicio={data_inicio}, data_fim={fim_plus_one}")
            
            debug_sql = text("""
                SELECT COUNT(*) as total
                FROM pedidos 
                WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    LOWER(cliente), 
                    'ç', 'c'), 'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'é', 'e'), 'ê', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')
                    LIKE :cliente_pattern
                  AND data_entrega IS NOT NULL
                  AND data_entrega >= :data_inicio
                  AND data_entrega < :data_fim
            """,
            )
            
            debug_result = await session.execute(
                debug_sql, 
                {
                    "cliente_pattern": cliente_pattern,
                    "data_inicio": data_inicio,
                    "data_fim": fim_plus_one
                }
            )
            debug_count = debug_result.scalar()
            logger.info(f"[listar_pedidos] 🔍 DEBUG SQL direto (normalizado) encontrou: {debug_count} pedido(s)")
            
            # Testar sem o filtro de cliente para verificar se o problema é o LIKE
            debug_sql2 = text("""
                SELECT COUNT(*) as total
                FROM pedidos 
                WHERE data_entrega IS NOT NULL
                  AND data_entrega >= :data_inicio
                  AND data_entrega < :data_fim
            """,
            )
            debug_result2 = await session.execute(
                debug_sql2, 
                {
                    "data_inicio": data_inicio,
                    "data_fim": fim_plus_one
                }
            )
            debug_count2 = debug_result2.scalar()
            logger.info(f"[listar_pedidos] 🔍 DEBUG SQL SEM filtro cliente encontrou: {debug_count2} pedido(s)")
            
            # Testar só com o filtro de cliente
            debug_sql3 = text("""
                SELECT COUNT(*) as total
                FROM pedidos 
                WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    LOWER(cliente), 
                    'ç', 'c'), 'á', 'a'), 'à', 'a'), 'ã', 'a'), 'â', 'a'), 'é', 'e'), 'ê', 'e'), 'í', 'i'), 'ó', 'o'), 'ú', 'u')
                    LIKE :cliente_pattern
            """,
            )
            debug_result3 = await session.execute(
                debug_sql3, 
                {
                    "cliente_pattern": cliente_pattern
                }
            )
            debug_count3 = debug_result3.scalar()
            logger.info(f"[listar_pedidos] 🔍 DEBUG SQL SÓ filtro cliente (normalizado) encontrou: {debug_count3} pedido(s)")
        
        result = await session.exec(filters)
        
        # Tentar carregar pedidos - se falhar, usar query raw para normalizar status primeiro
        try:
            pedidos_raw = result.all()
            # Normalizar status ANTES de qualquer operação que possa acionar validação
            pedidos = []
            for pedido in pedidos_raw:
                # Normalizar status imediatamente após carregar
                normalize_pedido_status(pedido)
                pedidos.append(pedido)
            
            logger.info(f"[listar_pedidos] Query executada com sucesso: {len(pedidos)} pedido(s) encontrado(s)")
        except Exception as load_error:
            # Se houver erro ao carregar (validação de enum), usar query SQL direta
            logger.warning(f"Erro ao carregar pedidos com SQLModel: {load_error}. Tentando query SQL direta...")
            
            # Construir query SQL manualmente
            where_clauses = []
            params = []
            param_idx = 1
            
            if status:
                where_clauses.append(f"status = ${param_idx}")
                params.append(status.value)
                param_idx += 1
            
            if cliente:
                where_clauses.append(f"LOWER(cliente) LIKE ${param_idx}")
                params.append(f"%{cliente.strip().lower()}%")
                param_idx += 1
            
            # Aplicar filtro de data conforme date_mode
            date_mode_normalized = (date_mode or "entrega").lower().strip()
            
            if data_inicio or data_fim:
                if date_mode_normalized == "entrada":
                    # Filtrar por data_entrada usando DATE() para extrair apenas a parte da data
                    if data_inicio:
                        where_clauses.append(f"DATE(data_entrada) >= ${param_idx}")
                        params.append(data_inicio)
                        param_idx += 1
                    if data_fim:
                        where_clauses.append(f"DATE(data_entrada) <= ${param_idx}")
                        params.append(data_fim)
                        param_idx += 1
                
                elif date_mode_normalized == "qualquer":
                    # Filtrar por qualquer uma das duas datas usando DATE()
                    if data_inicio and data_fim:
                        where_clauses.append(f"((DATE(data_entrada) >= ${param_idx} AND DATE(data_entrada) <= ${param_idx + 1}) OR (DATE(data_entrega) >= ${param_idx} AND DATE(data_entrega) <= ${param_idx + 1}))")
                        params.append(data_inicio)
                        params.append(data_fim)
                        param_idx += 2
                    elif data_inicio:
                        where_clauses.append(f"(DATE(data_entrada) >= ${param_idx} OR DATE(data_entrega) >= ${param_idx})")
                        params.append(data_inicio)
                        param_idx += 1
                    elif data_fim:
                        where_clauses.append(f"(DATE(data_entrada) <= ${param_idx} OR DATE(data_entrega) <= ${param_idx})")
                        params.append(data_fim)
                        param_idx += 1
                
                else:
                    # Padrão: filtrar por data_entrega usando DATE()
                    if data_inicio or data_fim:
                        where_clauses.append(f"data_entrega IS NOT NULL")
                    if data_inicio:
                        where_clauses.append(f"DATE(data_entrega) >= ${param_idx}")
                        params.append(data_inicio)
                        param_idx += 1
                    if data_fim:
                        where_clauses.append(f"DATE(data_entrega) <= ${param_idx}")
                        params.append(data_fim)
                        param_idx += 1
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Query SQL com normalização de status
            sql_query = text(f"""
                SELECT 
                    id, numero, data_entrada, COALESCE(data_entrega, data_entrada) as data_entrega,
                    observacao, prioridade,
                    CASE LOWER(COALESCE(status, 'pendente'))
                        WHEN 'pendente' THEN 'pendente'
                        WHEN 'em producao' THEN 'em_producao'
                        WHEN 'em produção' THEN 'em_producao'
                        WHEN 'em_producao' THEN 'em_producao'
                        WHEN 'pronto' THEN 'pronto'
                        WHEN 'entregue' THEN 'entregue'
                        WHEN 'concluido' THEN 'entregue'
                        WHEN 'concluído' THEN 'entregue'
                        WHEN 'cancelado' THEN 'cancelado'
                        ELSE 'pendente'
                    END as status,
                    cliente, telefone_cliente, cidade_cliente,
                    valor_total, valor_frete, valor_itens,
                    tipo_pagamento, obs_pagamento, forma_envio, forma_envio_id,
                    financeiro, conferencia, sublimacao, costura, expedicao, pronto,
                    sublimacao_maquina, sublimacao_data_impressao, items,
                    data_criacao, ultima_atualizacao
                FROM pedidos
                WHERE {where_sql}
                ORDER BY data_criacao DESC
                LIMIT {limit} OFFSET {skip}
            """,
            )
            
            # Executar query e criar objetos Pedido manualmente
            raw_result = await session.execute(sql_query, params)
            rows = raw_result.fetchall()
            
            pedidos = []
            for row in rows:
                try:
                    # Criar objeto Pedido a partir da row
                    pedido_dict = {
                        'id': row[0],
                        'numero': row[1],
                        'data_entrada': row[2],
                        'data_entrega': row[3],
                        'observacao': row[4],
                        'prioridade': row[5],
                        'status': Status(row[6]),  # Status já normalizado na query
                        'cliente': row[7],
                        'telefone_cliente': row[8],
                        'cidade_cliente': row[9],
                        'valor_total': row[10],
                        'valor_frete': row[11],
                        'valor_itens': row[12],
                        'tipo_pagamento': row[13],
                        'obs_pagamento': row[14],
                        'forma_envio': row[15],
                        'forma_envio_id': row[16],
                        'financeiro': bool(row[17]),
                        'conferencia': bool(row[18]),
                        'sublimacao': bool(row[19]),
                        'costura': bool(row[20]),
                        'expedicao': bool(row[21]),
                        'pronto': bool(row[22]),
                        'sublimacao_maquina': row[23],
                        'sublimacao_data_impressao': row[24],
                        'items': row[25],
                        'data_criacao': row[26],
                        'ultima_atualizacao': row[27],
                    }
                    pedido = Pedido(**pedido_dict)
                    pedidos.append(pedido)
                except Exception as e:
                    logger.error(f"Erro ao criar pedido da row: {e}", exc_info=True)
                    continue
        
        # Converter items de JSON string para objetos (otimizado: batch)
        pedidos_items: dict[int, List[ItemPedido]] = {}
        for pedido in pedidos:
            if pedido.id is not None:
                items = json_string_to_items(pedido.items)
                pedidos_items[pedido.id] = items
        
        # Buscar todas as imagens de uma vez (evita N+1 queries)
        await populate_items_with_image_paths_batch(session, pedidos, pedidos_items)
        
        # Montar resposta - criar PedidoResponse diretamente do objeto
        response_pedidos = []
        for pedido in pedidos:
            try:
                items = pedidos_items.get(pedido.id, []) if pedido.id is not None else []
                pedido_data = pedido_to_response_dict(pedido, items)
                response_pedido = PedidoResponse(**pedido_data)
                response_pedidos.append(response_pedido)
            except Exception as e:
                logger.error(f"Erro ao processar pedido {pedido.id if hasattr(pedido, 'id') and pedido.id else 'unknown'}: {e}", exc_info=True)
                # Continuar com próximo pedido
                continue
        
        return response_pedidos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao listar pedidos")
        raise HTTPException(status_code=500, detail="Erro interno ao listar pedidos")


@router.get("/total")
async def contar_total_pedidos(
    session: AsyncSession = Depends(get_session),
    status: Optional[Status] = Query(default=None),
    cliente: Optional[str] = Query(default=None),
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada', 'entrega' ou 'qualquer'"),
):
    """
    Retorna o total de pedidos registrados no banco de dados com suporte a filtros.
    """
    try:
        filters = select(func.count(Pedido.id))
        
        if status:
            filters = filters.where(Pedido.status == status)

        if cliente:
            import unicodedata
            cliente_normalized = unicodedata.normalize('NFKD', cliente.strip().lower())
            cliente_normalized = ''.join(c for c in cliente_normalized if not unicodedata.combining(c))
            search = f"%{cliente_normalized}%"
            
            cliente_col_normalized = func.lower(Pedido.cliente)
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ç', 'c')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'á', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'à', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ã', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'â', 'a')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'é', 'e')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ê', 'e')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'í', 'i')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ó', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ô', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'õ', 'o')
            cliente_col_normalized = func.replace(cliente_col_normalized, 'ú', 'u')
            
            filters = filters.where(cliente_col_normalized.like(search))

        data_inicio = _validate_iso_date(data_inicio, "data_inicio")
        data_fim = _validate_iso_date(data_fim, "data_fim")

        if data_inicio or data_fim:
            date_mode_normalized = (date_mode or "entrada").lower().strip()
            
            if date_mode_normalized == "entrada":
                if data_inicio:
                    filters = filters.where(func.date(Pedido.data_entrada) >= data_inicio)
                if data_fim:
                    filters = filters.where(func.date(Pedido.data_entrada) <= data_fim)
            
            elif date_mode_normalized == "qualquer":
                if data_inicio and data_fim:
                    filters = filters.where(
                        or_(
                            and_(
                                func.date(Pedido.data_entrada) >= data_inicio,
                                func.date(Pedido.data_entrada) <= data_fim
                            ),
                            and_(
                                func.date(Pedido.data_entrega) >= data_inicio,
                                func.date(Pedido.data_entrega) <= data_fim
                            )
                        )
                    )
                elif data_inicio:
                    filters = filters.where(
                        or_(func.date(Pedido.data_entrada) >= data_inicio, func.date(Pedido.data_entrega) >= data_inicio)
                    )
                elif data_fim:
                    filters = filters.where(
                        or_(func.date(Pedido.data_entrada) <= data_fim, func.date(Pedido.data_entrega) <= data_fim)
                    )
            
            else:
                if data_inicio or data_fim:
                    filters = filters.where(Pedido.data_entrega.isnot(None))
                if data_inicio:
                    filters = filters.where(func.date(Pedido.data_entrega) >= data_inicio)
                if data_fim:
                    filters = filters.where(func.date(Pedido.data_entrega) <= data_fim)

        result = await session.execute(filters)
        total = result.scalar() or 0
        
        return {"total": total}
        
    except Exception as e:
        logger.exception("Erro ao contar total de pedidos")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_shipping_methods_summary(session: AsyncSession):
    """Auxiliar para obter distribuição de formas de envio."""
    try:
        query = select(Pedido.forma_envio, func.count(Pedido.id)).group_by(Pedido.forma_envio).order_by(func.count(Pedido.id).desc()).limit(5)
        result = await session.execute(query)
        rows = result.all()
        
        total_query = select(func.count(Pedido.id))
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 1
        
        return [
            {
                "name": row[0] or "Não especificado",
                "count": row[1],
                "percentage": int((row[1] / total) * 100)
            } for row in rows
        ]
    except Exception:
        return []


@router.get("/summary")
async def obter_resumo_pedidos(
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna um resumo estatístico dos pedidos para o dashboard.
    """
    try:
        # 1. Contagem por status
        # SELECT status, COUNT(*) FROM pedidos GROUP BY status
        status_query = select(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status)
        result = await session.execute(status_query)
        rows = result.all()
        
        # Mapear resultados para dicionário de contagem
        counts = {s: 0 for s in Status}
        total = 0
        
        for status_val, count in rows:
            if status_val in counts:
                counts[status_val] = count
            total += count

        # 2. Pedidos Atrasados
        # Pedidos que não estão prontos, entregues ou cancelados e cuja data de entrega já passou
        today = datetime.utcnow().date().isoformat()
        atrasados_query = select(func.count(Pedido.id)).where(
            and_(
                Pedido.status != Status.PRONTO,
                Pedido.status != Status.ENTREGUE,
                Pedido.status != Status.CANCELADO,
                Pedido.data_entrega.isnot(None),
                func.date(Pedido.data_entrega) < today
            )
        )
        atrasados_result = await session.execute(atrasados_query)
        atrasados_count = atrasados_result.scalar() or 0

        # 3. Pedidos Urgentes
        urgentes_query = select(func.count(Pedido.id)).where(
            and_(
                Pedido.status != Status.PRONTO,
                Pedido.status != Status.ENTREGUE,
                Pedido.status != Status.CANCELADO,
                Pedido.prioridade == "ALTA"
            )
        )
        urgentes_result = await session.execute(urgentes_query)
        urgentes_count = urgentes_result.scalar() or 0

        # 4. Pedidos Criados Hoje
        hoje_query = select(func.count(Pedido.id)).where(
            or_(
                func.date(Pedido.data_entrada) == today,
                func.date(Pedido.data_criacao) == today
            )
        )
        hoje_result = await session.execute(hoje_query)
        hoje_count = hoje_result.scalar() or 0

        # 5. Taxa de Eficiência (Pedidos concluídos no prazo / Total concluídos)
        concluidos_count = counts.get(Status.PRONTO, 0) + counts.get(Status.ENTREGUE, 0)
        eficiencia = 0
        avg_production_time = 0
        
        if concluidos_count > 0:
            # Pedidos concluídos no prazo
            on_time_query = select(func.count(Pedido.id)).where(
                and_(
                    or_(Pedido.status == Status.PRONTO, Pedido.status == Status.ENTREGUE),
                    Pedido.data_entrega.isnot(None),
                    func.date(Pedido.ultima_atualizacao) <= func.date(Pedido.data_entrega)
                )
            )
            on_time_result = await session.execute(on_time_query)
            on_time_count = on_time_result.scalar() or 0
            eficiencia = int((on_time_count / concluidos_count) * 100)

            # Tempo médio de produção (em dias)
            time_query = select(func.avg(
                func.julianday(Pedido.ultima_atualizacao) - func.julianday(Pedido.data_entrada)
            )).where(
                and_(
                    or_(Pedido.status == Status.PRONTO, Pedido.status == Status.ENTREGUE),
                    Pedido.data_entrada.isnot(None)
                )
            )
            time_result = await session.execute(time_query)
            avg_production_time = round(time_result.scalar() or 0)

        # 5b. Tempo médio de atraso (pedidos não concluídos e já passados do prazo)
        delay_query = select(func.avg(
            func.julianday('now') - func.julianday(Pedido.data_entrega)
        )).where(
            and_(
                Pedido.status != Status.PRONTO,
                Pedido.status != Status.ENTREGUE,
                Pedido.status != Status.CANCELADO,
                Pedido.data_entrega.isnot(None),
                func.date(Pedido.data_entrega) < func.date('now')
            )
        )
        delay_result = await session.execute(delay_query)
        avg_delay_time = round(delay_result.scalar() or 0)

        # 6. Eficiência por Etapa
        # Contagem de pedidos que passaram por cada etapa (financeiro, conferencia, etc)
        # em relação ao total de pedidos não cancelados
        total_active = total - counts.get(Status.CANCELADO, 0)
        total_active = max(total_active, 1)
        
        stages_query = select(
            func.count(case((Pedido.financeiro == True, 1))),
            func.count(case((Pedido.conferencia == True, 1))),
            func.count(case((Pedido.sublimacao == True, 1))),
            func.count(case((Pedido.costura == True, 1))),
            func.count(case((Pedido.expedicao == True, 1))),
        ).where(Pedido.status != Status.CANCELADO)
        
        stages_result = await session.execute(stages_query)
        stages_counts = stages_result.one()
        
        production_efficiency = {
            "financeiro": int((stages_counts[0] / total_active) * 100),
            "conferencia": int((stages_counts[1] / total_active) * 100),
            "sublimacao": int((stages_counts[2] / total_active) * 100),
            "costura": int((stages_counts[3] / total_active) * 100),
            "expedicao": int((stages_counts[4] / total_active) * 100),
        }

        # 7. Pedidos recentes (últimos 5 por data_criacao) e urgentes (5 ALTA não prontos por data_entrega)
        async def _pedidos_to_response_dicts(pedidos_list: List[Pedido]) -> List[dict]:
            if not pedidos_list:
                return []
            pedidos_items: dict[int, List[ItemPedido]] = {}
            for p in pedidos_list:
                if p.id is not None:
                    pedidos_items[p.id] = json_string_to_items(p.items or "[]")
            await populate_items_with_image_paths_batch(session, pedidos_list, pedidos_items)
            out = []
            for p in pedidos_list:
                items = pedidos_items.get(p.id, []) if p.id is not None else []
                try:
                    d = pedido_to_response_dict(p, items)
                    resp = PedidoResponse(**d)
                    out.append(jsonable_encoder(resp))
                except Exception as e:
                    logger.warning("Erro ao serializar pedido %s no summary: %s", p.id, e)
            return out

        recent_stmt = (
            select(Pedido)
            .where(Pedido.status != Status.CANCELADO)
            .order_by(Pedido.data_criacao.desc())
            .limit(5)
        )
        recent_result = await session.exec(recent_stmt)
        recent_pedidos = list(recent_result.all())
        for p in recent_pedidos:
            normalize_pedido_status(p)

        urgent_stmt = (
            select(Pedido)
            .where(
                and_(
                    Pedido.prioridade == "ALTA",
                    Pedido.status != Status.PRONTO,
                    Pedido.status != Status.ENTREGUE,
                    Pedido.status != Status.CANCELADO,
                )
            )
            .order_by(Pedido.data_entrega.asc())
            .limit(5)
        )
        urgent_result = await session.exec(urgent_stmt)
        urgent_pedidos = list(urgent_result.all())
        for p in urgent_pedidos:
            normalize_pedido_status(p)

        recent_orders = await _pedidos_to_response_dicts(recent_pedidos)
        urgent_orders = await _pedidos_to_response_dicts(urgent_pedidos)

        return {
            "total": total,
            "pendentes": counts.get(Status.PENDENTE, 0),
            "em_producao": counts.get(Status.EM_PRODUCAO, 0),
            "concluidos": concluidos_count,
            "atrasados": atrasados_count,
            "urgentes": urgentes_count,
            "hoje": hoje_count,
            "efficiency_rate": eficiencia,
            "avg_production_time": avg_production_time,
            "avg_delay_time": avg_delay_time,
            "production_efficiency": production_efficiency,
            "shipping_methods": await _get_shipping_methods_summary(session),
            "status_counts": {s.value: c for s, c in counts.items()},
            "recent_orders": recent_orders,
            "urgent_orders": urgent_orders,
        }
    except Exception as e:
        logger.exception("Erro ao gerar resumo de pedidos")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{pedido_id}", response_model=PedidoResponse)
async def obter_pedido(pedido_id: int, session: AsyncSession = Depends(get_session)):
    """
    Obtém um pedido específico por ID com seus items convertidos.
    """
    try:
        pedido = await session.get(Pedido, pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # Normalizar status ANTES de processar
        normalize_pedido_status(pedido)
        
        # Converter items de JSON string para objetos
        items = json_string_to_items(pedido.items)
        await populate_items_with_image_paths(session, pedido.id, items)

        pedido_data = pedido_to_response_dict(pedido, items)
        return PedidoResponse(**pedido_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao obter pedido %s", pedido_id)
        raise HTTPException(status_code=500, detail="Erro interno ao obter pedido")

@router.post("/batch-status")
async def batch_atualizar_status(
    update: BatchStatusUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Atualiza o status de múltiplos pedidos de uma vez.
    """
    try:
        # Buscar os pedidos
        stmt = select(Pedido).where(Pedido.id.in_(update.id_pedidos))
        result = await session.exec(stmt)
        pedidos = result.all()
        
        if not pedidos:
            raise HTTPException(status_code=404, detail="Nenhum pedido encontrado")
            
        for pedido in pedidos:
            pedido.status = update.status
            pedido.ultima_atualizacao = datetime.utcnow()
            
            # Se status for ENTREGUE ou PRONTO, sincronizar flags se necessário
            if update.status == Status.ENTREGUE:
                pedido.pronto = True

            await enqueue_sync_event(
                session,
                entity=SyncEntity.PEDIDO.value,
                event_type=SyncEventType.UPSERT.value,
                entity_id=pedido.id,
                payload={"pedido_id": pedido.id},
            )
            
        await session.commit()
        return {"count": len(pedidos), "status": update.status}
        
    except Exception as e:
        await session.rollback()
        logger.exception("Erro ao atualizar status em lote")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{pedido_id}", response_model=PedidoResponse)
async def atualizar_pedido(
    pedido_id: int,
    pedido_update: PedidoUpdate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    is_admin: bool = Depends(get_current_user_admin),
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Atualiza um pedido existente. Aceita atualizações parciais.
    Requer permissão de administrador para alterar campo 'financeiro'.
    Resistente a concorrência com retry logic e backoff exponencial.
    """
    MAX_RETRIES = 5
    
    # Preparar dados uma vez (fora do loop de retry)
    update_data = pedido_update.model_dump(exclude_unset=True)
    
    # Verificação de permissão (fora do loop)
    if 'financeiro' in update_data and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Somente administradores podem alterar o status financeiro."
        )
    
    # Preparar items (fora do loop)
    items_payload_for_images: Optional[List[dict[str, Any]]] = None
    pending_uploads: List[PendingImageUpload] = []
    pending_removals: List[PendingImageRemoval] = []
    if 'items' in update_data and update_data['items'] is not None:
        items_payload_for_images, pending_uploads, pending_removals = prepare_items_for_storage(
            update_data['items'],
            allow_removal=True
        )
        # ── Normalizar valor_unitario dos itens antes de persistir ───────────
        # Note: os totais do pedido (valor_total) serão calculados 
        # logo abaixo no loop de retry, após o merger com dados do banco.
        from .pricing import recalculate_items_totals
        items_payload_for_images = recalculate_items_totals(items_payload_for_images)
        # ─────────────────────────────────────────────────────────────────────
        update_data['items'] = items_to_json_string(items_payload_for_images)
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Re-buscar o pedido a cada tentativa (pode ter mudado)
            db_pedido = await session.get(Pedido, pedido_id)
            if not db_pedido:
                raise HTTPException(status_code=404, detail="Pedido não encontrado")
            
            # Normalizar status ANTES de capturar valores
            normalize_pedido_status(db_pedido)
            
            # 🔥 CAPTURAR VALORES ANTES DA ATUALIZAÇÃO para detectar mudanças reais
            status_fields_before = {
                "status": db_pedido.status,
                "financeiro": db_pedido.financeiro,
                "conferencia": db_pedido.conferencia,
                "sublimacao": db_pedido.sublimacao,
                "costura": db_pedido.costura,
                "expedicao": db_pedido.expedicao,
                "pronto": getattr(db_pedido, 'pronto', False),
            }
            
            # Preparar update_data local (pode precisar ajustes baseados no estado atual)
            local_update_data = dict(update_data)
            
            if 'data_entrega' in local_update_data and not local_update_data['data_entrega']:
                local_update_data['data_entrega'] = db_pedido.data_entrada

            if 'forma_envio_id' in local_update_data and local_update_data['forma_envio_id'] is None:
                local_update_data['forma_envio_id'] = db_pedido.forma_envio_id or 0

            if 'numero' in local_update_data and not local_update_data['numero']:
                if db_pedido.numero:
                    local_update_data['numero'] = db_pedido.numero
                else:
                    local_update_data['numero'] = await get_next_order_number(session)

            estado_update = (local_update_data.pop('estado_cliente', None) or '').strip()
            if 'cidade_cliente' in local_update_data or estado_update:
                cidade_atual, estado_atual = decode_city_state(db_pedido.cidade_cliente)
                nova_cidade = local_update_data.get('cidade_cliente', cidade_atual) or ''
                nova_cidade, _ = decode_city_state(nova_cidade)
                estado_final = estado_update if estado_update else estado_atual
                local_update_data['cidade_cliente'] = encode_city_state(nova_cidade, estado_final)

            items_anteriores = json_string_to_items(db_pedido.items or "[]")
            status_anterior_aplica_estoque = is_stock_eligible_status(db_pedido.status)
            status_novo_aplica_estoque = is_stock_eligible_status(
                local_update_data.get("status", db_pedido.status)
            )

            if items_payload_for_images is not None:
                items_novos_para_estoque: list[Any] = items_payload_for_images
            else:
                items_novos_para_estoque = items_anteriores

            consumo_anterior = (
                summarize_material_consumption(items_anteriores)
                if status_anterior_aplica_estoque
                else {}
            )
            consumo_novo = (
                summarize_material_consumption(items_novos_para_estoque)
                if status_novo_aplica_estoque
                else {}
            )
            if is_material_stock_enabled():
                delta_estoque = build_material_stock_delta(consumo_anterior, consumo_novo)
                await apply_material_stock_delta(session, delta_estoque)

            # Atualizar timestamp
            local_update_data['ultima_atualizacao'] = datetime.utcnow()

            # ── Recalcular totais do pedido (Guardrail) ──────────────────────
            # Garante consistência financeira recalculando valor_total sempre que
            # items ou frete são alterados.
            if items_payload_for_images is not None or 'valor_frete' in local_update_data:
                # Usar novos itens se enviados, senão usar os do banco
                target_items = items_payload_for_images if items_payload_for_images is not None else items_anteriores
                
                valor_frete_efetivo = (
                    local_update_data.get("valor_frete")
                    if 'valor_frete' in local_update_data
                    else getattr(db_pedido, "valor_frete", "0.00")
                )
                
                _, totais = normalize_order_financials(target_items, valor_frete_efetivo)
                local_update_data["valor_itens"] = totais["valor_itens"]
                local_update_data["valor_total"] = totais["valor_total"]
            # ── Guardrail para financeiro_liberado_em ────────────────────────
            if 'financeiro' in local_update_data:
                novo_val = local_update_data['financeiro']
                if novo_val and not db_pedido.financeiro:
                    local_update_data['financeiro_liberado_em'] = datetime.now(timezone.utc)
                elif not novo_val and db_pedido.financeiro:
                    local_update_data['financeiro_liberado_em'] = None
            # ─────────────────────────────────────────────────────────────────

            # Aplicar atualizações
            for field, value in local_update_data.items():
                setattr(db_pedido, field, value)
            
            session.add(db_pedido)
            if items_payload_for_images is not None:
                if await apply_image_changes(
                    session,
                    db_pedido.id,
                    pending_uploads,
                    pending_removals,
                    items_payload_for_images,
                ):
                    db_pedido.items = items_to_json_string(items_payload_for_images)

            await enqueue_sync_event(
                session,
                entity=SyncEntity.PEDIDO.value,
                event_type=SyncEventType.UPSERT.value,
                entity_id=db_pedido.id,
                payload={"pedido_id": db_pedido.id},
            )
            await session.commit()
            await session.refresh(db_pedido)
            
            # 🔥 CAPTURAR VALORES DEPOIS DA ATUALIZAÇÃO
            status_fields_after = {
                "status": db_pedido.status,
                "financeiro": db_pedido.financeiro,
                "conferencia": db_pedido.conferencia,
                "sublimacao": db_pedido.sublimacao,
                "costura": db_pedido.costura,
                "expedicao": db_pedido.expedicao,
                "pronto": getattr(db_pedido, 'pronto', False),
            }
            
            # 🔥 DETECTAR MUDANÇAS REAIS DE STATUS (comparar antes vs depois)
            status_changed = any(
                status_fields_before.get(key) != status_fields_after.get(key)
                for key in status_fields_before.keys()
            )
            
            if __debug__ and status_changed:
                changed_fields = [
                    key for key in status_fields_before.keys()
                    if status_fields_before.get(key) != status_fields_after.get(key)
                ]
                print(f"[Pedidos] Mudança de status detectada no pedido {pedido_id}: {changed_fields}")
                print(f"[Pedidos] Antes: {status_fields_before}")
                print(f"[Pedidos] Depois: {status_fields_after}")
            
            # Converter de volta para response
            items = json_string_to_items(db_pedido.items or "[]")
            await populate_items_with_image_paths(session, db_pedido.id, items)
            
            # Normalizar status após refresh (pode ter voltado como string do banco)
            normalize_pedido_status(db_pedido)
            
            pedido_data = pedido_to_response_dict(db_pedido, items)
            response = PedidoResponse(**pedido_data)
            
            # Obter informações do usuário atual para incluir no broadcast
            user_info = await get_current_user_from_token(token, session)
            
            # 🔥 SEMPRE ENVIAR order_updated quando há qualquer atualização
            if __debug__:
                logger.debug("[Pedidos] Enviando broadcast 'order_updated' para pedido %s", pedido_id)
            # 🔥 Garantir JSON atualizado ANTES do broadcast (evita /json stale nos clientes)

            await _save_pedido_json_internal(pedido_id, jsonable_encoder(response))

            broadcast_order_event("order_updated", response, None, user_info)
            
            # 🔥 ENVIAR order_status_updated APENAS quando há mudança real de status
            if status_changed:
                if __debug__:
                    logger.debug("[Pedidos] Enviando broadcast 'order_status_updated' para pedido %s", pedido_id)
                broadcast_order_event("order_status_updated", response, None, user_info)
            
            # Sincronizar com a VPS (Background) após qualquer atualização bem-sucedida
            background_tasks.add_task(vps_sync_service.sync_pedido, response)

            return response
            
        except HTTPException:
            await session.rollback()
            raise
        except IntegrityError as exc:
            await session.rollback()
            msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
            if "uq_pedidos_numero" in msg or "unique" in msg or "numero" in msg:
                if attempt >= MAX_RETRIES:
                    logger.error(
                        "Conflito de numero ao atualizar pedido id=%s após %s tentativas: %s",
                        pedido_id,
                        attempt,
                        exc,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail="Já existe um pedido com este numero.",
                    ) from exc
                logger.warning(
                    "Conflito de numero ao atualizar pedido id=%s, tentando novamente (tentativa %s)",
                    pedido_id,
                    attempt,
                )
                await asyncio.sleep(0.1 * attempt)  # Backoff exponencial
                continue
            logger.error("Erro de integridade ao atualizar pedido %s: %s", pedido_id, exc)
            raise HTTPException(status_code=400, detail=f"Erro de integridade ao atualizar pedido: {str(exc)}") from exc
        except OperationalError as exc:
            await session.rollback()
            msg = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
            if "database is locked" in msg:
                if attempt >= MAX_RETRIES:
                    logger.error("Banco de dados locked ao atualizar pedido id=%s após %s tentativas: %s", pedido_id, attempt, exc)
                    raise HTTPException(
                        status_code=503,
                        detail="Banco de dados temporariamente ocupado. Tente novamente em instantes.",
                    ) from exc
                logger.warning("database is locked ao atualizar pedido id=%s, tentando novamente (tentativa %s)", pedido_id, attempt)
                await asyncio.sleep(0.1 * attempt)  # Backoff exponencial
                continue
            logger.error("Erro de banco ao atualizar pedido %s: %s", pedido_id, exc)
            raise HTTPException(status_code=400, detail="Erro interno ao processar atualização do pedido") from exc
        except Exception as exc:
            await session.rollback()
            logger.exception("Erro inesperado ao atualizar pedido %s: %s", pedido_id, exc)
            raise HTTPException(status_code=400, detail="Erro interno ao atualizar pedido") from exc

@router.delete("/{pedido_id}")
async def deletar_pedido(
    pedido_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: bool = Depends(require_admin)
):
    """
    Deleta um pedido existente.
    Requer permissão de administrador.
    """
    try:
        db_pedido = await session.get(Pedido, pedido_id)
        if not db_pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        # Tabela PedidoResponse para o sync (antes de deletar)
        items = json_string_to_items(db_pedido.items or "[]")
        await populate_items_with_image_paths(session, pedido_id, items)
        pedido_res = PedidoResponse(**pedido_to_response_dict(db_pedido, items))

        if is_material_stock_enabled() and is_stock_eligible_status(db_pedido.status):
            consumo_atual = summarize_material_consumption(items)
            delta_retorno = build_material_stock_delta(consumo_atual, {})
            await apply_material_stock_delta(session, delta_retorno)

        images_result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido_id))
        for image in images_result.all():
            await delete_media_file(image.path)
            await session.delete(image)
        
        await session.delete(db_pedido)
        await enqueue_sync_event(
            session,
            entity=SyncEntity.PEDIDO.value,
            event_type=SyncEventType.DELETE.value,
            entity_id=pedido_id,
            payload={"pedido_id": pedido_id},
        )
        await session.commit()
        broadcast_order_event("order_deleted", order_id=pedido_id)

        # Sincronizar deleção com a VPS
        background_tasks.add_task(vps_sync_service.sync_deletion, pedido_res)

        return {"message": "Pedido deletado com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Erro ao deletar pedido %s", pedido_id)
        raise HTTPException(status_code=500, detail="Erro interno ao deletar pedido")

@router.delete("/all")
async def deletar_todos_pedidos(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _admin: bool = Depends(require_admin)
):
    """
    Deleta todos os pedidos e suas imagens.
    Requer permissão de administrador.
    """
    try:
        # Buscar todos os pedidos para deletar suas imagens
        result = await session.exec(select(Pedido))
        all_pedidos = result.all()

        # Preparar dados para o sync antes de deletar
        pedidos_para_sync = []
        consumo_total_ativo: dict[str, float] = {}
        for pedido in all_pedidos:
            items = json_string_to_items(pedido.items or "[]")
            await populate_items_with_image_paths(session, pedido.id, items)
            pedidos_para_sync.append(PedidoResponse(**pedido_to_response_dict(pedido, items)))
            if is_stock_eligible_status(pedido.status):
                consumo_pedido = summarize_material_consumption(items)
                for nome_material, quantidade in consumo_pedido.items():
                    consumo_total_ativo[nome_material] = consumo_total_ativo.get(nome_material, 0.0) + quantidade

        if is_material_stock_enabled() and consumo_total_ativo:
            delta_retorno_total = build_material_stock_delta(consumo_total_ativo, {})
            await apply_material_stock_delta(session, delta_retorno_total)

        # Deletar imagens de todos os pedidos
        for pedido in all_pedidos:
            images_result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido.id))
            for image in images_result.all():
                await delete_media_file(image.path)
                await session.delete(image)
        
        # Deletar todos os pedidos (os itens serão deletados em cascata)
        for pedido in all_pedidos:
            await session.delete(pedido)
            await enqueue_sync_event(
                session,
                entity=SyncEntity.PEDIDO.value,
                event_type=SyncEventType.DELETE.value,
                entity_id=pedido.id,
                payload={"pedido_id": pedido.id},
            )
        
        await session.commit()
        broadcast_order_event("order_deleted", order_id=None)

        # Sincronizar deleção em massa (para cada pedido)
        for pedido_res in pedidos_para_sync:
            background_tasks.add_task(vps_sync_service.sync_deletion, pedido_res)

        return {"message": "Todos os pedidos foram deletados com sucesso"}
        
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar todos os pedidos: {str(e)}")

@router.get("/status/{status}", response_model=List[PedidoResponse])
async def listar_pedidos_por_status(status: str, session: AsyncSession = Depends(get_session)):
    """
    Lista pedidos por status específico.
    """
    try:
        from .schema import Status
        try:
            status_enum = Status(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Status inválido: {status}")
        
        result = await session.exec(select(Pedido).where(Pedido.status == status_enum))
        pedidos = result.all()
        
        # Normalizar status dos pedidos ANTES de processar
        for pedido in pedidos:
            normalize_pedido_status(pedido)
        
        # Converter items de JSON string para objetos (otimizado: batch)
        pedidos_items: dict[int, List[ItemPedido]] = {}
        for pedido in pedidos:
            if pedido.id is not None:
                items = json_string_to_items(pedido.items)
                pedidos_items[pedido.id] = items
        
        # Buscar todas as imagens de uma vez (evita N+1 queries)
        await populate_items_with_image_paths_batch(session, pedidos, pedidos_items)
        
        # Montar resposta
        response_pedidos = []
        for pedido in pedidos:
            try:
                items = pedidos_items.get(pedido.id, []) if pedido.id is not None else []
                pedido_data = pedido_to_response_dict(pedido, items)
                response_pedido = PedidoResponse(**pedido_data)
                response_pedidos.append(response_pedido)
            except Exception as e:
                logger.error(f"Erro ao processar pedido {pedido.id if hasattr(pedido, 'id') and pedido.id else 'unknown'}: {e}", exc_info=True)
                continue
        
        return response_pedidos
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos por status: {str(e)}")


@router.patch("/pedido-itens/{item_id}")
async def update_pedido_item(
    item_id: int,
    payload: dict = Body(...),
    session: AsyncSession = Depends(get_session),
    #user: User = Depends(get_current_user) # Opcional: validar user
):
    """
    Atualiza um item específico dentro do JSON de itens de um pedido.
    Como os itens não são tabelas separadas, precisamos:
    1. Encontrar o pedido que contém este item_id
    2. Atualizar o item específico
    3. Salvar o pedido inteiro novamente
    """
    from .utils import find_order_by_item_id

    pedido_id = payload.pop("pedido_id", None)
    if pedido_id is not None:
        try:
            pedido_id = int(pedido_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="pedido_id inválido.")

    if pedido_id is not None:
        pedido = await session.get(Pedido, pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")

        items = json_string_to_items(pedido.items)
        index = None
        item = None
        for i, candidate in enumerate(items):
            if candidate.id == item_id:
                index = i
                item = candidate
                break
            if candidate.id is None and pedido.id is not None:
                fallback_id = pedido.id * 1000 + i
                if fallback_id == item_id:
                    index = i
                    item = candidate
                    break
    else:
        pedido, index, item = await find_order_by_item_id(session, item_id)
    
    if not pedido:
        raise HTTPException(status_code=404, detail=f"Item {item_id} não encontrado em nenhum pedido.")
    if index is None or item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} não encontrado no pedido informado.")
        
    # Atualizar campos do item
    current_data = item.model_dump()
    updated_data = {**current_data, **payload}
    
    # Validar tipos (o frontend manda string, mas schema pode ter int/float)
    # A conversão básica é feita pelo Pydantic ao recriar o objeto
    
    # Atualizar o item na lista do pedido
    # Primeiro deserializamos todos (já feito em find_order_by_item_id mas precisamos da lista completa)
    items = json_string_to_items(pedido.items)
    items_antes = list(items)
    
    # Recriar o item com os novos dados
    # Importante: manter o ID original
    updated_data['id'] = item_id 
    
    # Atualizar no array
    # Como ItemPedido é Pydantic, podemos instanciar ou usar dict. 
    # O json_string_to_items retorna objetos ItemPedido.
    # Vamos converter o dict atualizado para o objeto ItemPedido
    try:
        logger.info(f"Atualizando item {item_id} com payload: {payload}")
        new_item = ItemPedido(**updated_data)
        logger.info(f"Novo item criado: {new_item.model_dump()}")
        items[index] = new_item
    except Exception as e:
        logger.error(f"Erro ao validar item atualizado: {e}")
        raise HTTPException(status_code=400, detail=f"Dados inválidos para o item: {str(e)}")
    
    # Serializar de volta para JSON e salvar pedido
    if is_material_stock_enabled() and is_stock_eligible_status(pedido.status):
        consumo_antes = summarize_material_consumption(items_antes)
        consumo_depois = summarize_material_consumption(items)
        delta_estoque = build_material_stock_delta(consumo_antes, consumo_depois)
        await apply_material_stock_delta(session, delta_estoque)

    pedido.items = items_to_json_string(items)
    pedido.ultima_atualizacao = datetime.utcnow()
    
    session.add(pedido)
    
    # Criar log de impressão se machine_id ou data_impressao estiverem presentes no payload
    new_machine_id = payload.get("machine_id")
    new_date = payload.get("data_impressao")
    
    if (new_machine_id or new_date):
        try:
            from maquinas.print_log_schema import PrintLog, PrintLogStatus
            
            # Decidir qual machine_id usar
            m_id = None
            if new_machine_id and isinstance(new_machine_id, (int, str)):
                m_id = int(new_machine_id)
            elif new_item.machine_id:
                m_id = int(new_item.machine_id)
                
            if m_id and m_id > 0:
                # Verificar se já existe um log para este item
                query = select(PrintLog).where(
                    PrintLog.pedido_id == pedido.id,
                    PrintLog.item_id == item_id
                )
                result = await session.exec(query)
                db_log = result.first()

                if db_log:
                    # Atualiza log existente
                    db_log.printer_id = m_id
                    db_log.status = PrintLogStatus.SUCCESS
                    db_log.created_at = datetime.utcnow()
                    session.add(db_log)
                    logger.info(f"Log de produção atualizado automaticamente para item {item_id} na máquina {m_id}")
                else:
                    # Cria novo log
                    print_log = PrintLog(
                        printer_id=m_id,
                        pedido_id=pedido.id,
                        item_id=item_id,
                        status=PrintLogStatus.SUCCESS
                    )
                    session.add(print_log)
                    logger.info(f"Novo log de produção registrado automaticamente para item {item_id} na máquina {m_id}")
        except Exception as log_error:
            # Não falhar o update se o log der erro, mas avisar
            logger.warning(f"Erro ao criar log de produção automático: {log_error}")

    await session.commit()
    await session.refresh(pedido)
    
    return {"status": "success", "message": "Item atualizado", "item": new_item}

from dataclasses import dataclass
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text, func
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
)
from .realtime import schedule_broadcast
from datetime import datetime
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
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="ignored", auto_error=False)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

# Variável global para rastrear o último ID de pedido criado
ULTIMO_PEDIDO_ID = 0

STATE_SEPARATOR = "||"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass
class PendingImageUpload:
    index: int
    identifier: Optional[str]
    data_url: str


@dataclass
class PendingImageRemoval:
    index: int
    identifier: Optional[str]


async def ensure_order_columns() -> None:
    required = (
        ('conferencia', "ALTER TABLE pedidos ADD COLUMN conferencia BOOLEAN DEFAULT 0"),
        ('sublimacao_maquina', "ALTER TABLE pedidos ADD COLUMN sublimacao_maquina TEXT"),
        ('sublimacao_data_impressao', "ALTER TABLE pedidos ADD COLUMN sublimacao_data_impressao TEXT"),
        ('pronto', "ALTER TABLE pedidos ADD COLUMN pronto BOOLEAN DEFAULT 0"),
    )

    def _apply_columns(sync_conn):
        columns = sync_conn.execute(text("PRAGMA table_info(pedidos)")).fetchall()
        existing = {col[1] for col in columns}
        for name, ddl in required:
            if name not in existing:
                sync_conn.execute(text(ddl))

    try:
        async with engine.begin() as conn:
            await conn.run_sync(_apply_columns)
    except Exception as exc:
        print(f"[pedidos] aviso ao garantir colunas obrigatórias: {exc}")


async def ensure_order_indexes() -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_numero ON pedidos(numero)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_data_entrada ON pedidos(data_entrada)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_data_entrega ON pedidos(data_entrega)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente)",
    )

    def _apply_indexes(sync_conn):
        for ddl in statements:
            sync_conn.execute(text(ddl))

    try:
        async with engine.begin() as conn:
            await conn.run_sync(_apply_indexes)
    except Exception as exc:
        print(f"[pedidos] aviso ao garantir indices: {exc}")


async def ensure_order_schema() -> None:
    await ensure_order_columns()
    await ensure_order_indexes()


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


def build_api_path(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    prefix = (settings.API_V1_STR or "").strip()
    if not prefix:
        return normalized
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return f"{prefix.rstrip('/')}{normalized}"


def normalize_acabamento(acabamento_value: Any) -> Optional[Acabamento]:
    if isinstance(acabamento_value, Acabamento):
        return acabamento_value
    if isinstance(acabamento_value, dict):
        return Acabamento(**acabamento_value)
    return None


def item_to_plain_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, 'model_dump'):
        item_dict = item.model_dump(exclude_none=True, exclude_unset=True)
        acabamento = getattr(item, 'acabamento', None)
        if acabamento:
            normalized = normalize_acabamento(acabamento)
            if normalized:
                item_dict['acabamento'] = normalized.model_dump(exclude_none=True)
    elif isinstance(item, dict):
        item_dict = item.copy()
        acabamento_value = item_dict.get('acabamento')
        if hasattr(acabamento_value, 'model_dump'):
            item_dict['acabamento'] = acabamento_value.model_dump(exclude_none=True)
        elif isinstance(acabamento_value, dict):
            item_dict['acabamento'] = Acabamento(**acabamento_value).model_dump(exclude_none=True)
    else:
        item_dict = getattr(item, '__dict__', {}).copy()
    return item_dict


def items_to_json_string(items) -> str:
    """Converte lista de items para string JSON"""
    items_data = [item_to_plain_dict(item) for item in items]
    return orjson.dumps(items_data).decode("utf-8")

def json_string_to_items(items_json: str) -> List[ItemPedido]:
    """Converte string JSON para lista de items"""
    if not items_json:
        return []
    
    try:
        items_data = orjson.loads(items_json)
        normalized_items: List[ItemPedido] = []
        for item_data in items_data:
            acabamento = normalize_acabamento(item_data.get('acabamento'))
            payload = {k: v for k, v in item_data.items() if k != 'acabamento'}
            normalized_items.append(ItemPedido(**payload, acabamento=acabamento))
        return normalized_items
    except (orjson.JSONDecodeError, Exception) as e:
        print(f"Erro ao converter JSON para items: {e}")
        return []


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
            elif (
                allow_removal
                and identifier
                and (image_value is None or (isinstance(image_value, str) and not image_value.strip()))
            ):
                pending_removals.append(PendingImageRemoval(index, identifier))
                item_dict['imagem'] = None
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
    if not uploads and not removals:
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
        delete_media_file(record.path)
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

    for upload in uploads:
        record = _pop_matching(upload.identifier, upload.index)
        if record:
            await _remove_image(record)
        try:
            binary_data, mime_type = decode_base64_image(upload.data_url)
        except ImageDecodingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        relative_path, filename, size = store_image_bytes(
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
        if 0 <= upload.index < len(items_payload):
            items_payload[upload.index]['imagem'] = url
        has_changes = True

    return has_changes


def ensure_pedido_defaults(pedido_data: dict) -> dict:
    """Garante campos obrigatórios com valores padrão."""
    numero = pedido_data.get('numero')
    if not numero:
        numero = str(int(datetime.utcnow().timestamp()))
    pedido_data['numero'] = numero

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


def encode_city_state(cidade: str, estado: Optional[str]) -> str:
    base_cidade, _ = decode_city_state(cidade)
    estado_normalized = (estado or '').strip()
    if estado_normalized:
        return f"{base_cidade}{STATE_SEPARATOR}{estado_normalized}"
    return base_cidade


def decode_city_state(value: Optional[str]) -> tuple[str, Optional[str]]:
    if not value:
        return '', None
    if STATE_SEPARATOR in value:
        cidade, estado = value.split(STATE_SEPARATOR, 1)
        cidade = cidade.strip()
        estado = estado.strip() or None
        return cidade, estado
    return value.strip(), None


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
        from pathlib import Path
        import json
        from datetime import datetime
        
        # Obter caminho do projeto (mesmo padrão usado em images.py)
        PROJECT_ROOT = Path(__file__).resolve().parent.parent
        from config import settings
        _configured_media_root = Path(settings.MEDIA_ROOT)
        if not _configured_media_root.is_absolute():
            MEDIA_ROOT = (PROJECT_ROOT / _configured_media_root).resolve()
        else:
            MEDIA_ROOT = _configured_media_root.resolve()
        
        # Criar diretório para o pedido
        pedido_dir = MEDIA_ROOT / "pedidos" / str(pedido_id)
        pedido_dir.mkdir(parents=True, exist_ok=True)
        
        # Criar nome do arquivo com timestamp
        timestamp = datetime.utcnow().isoformat().replace(':', '-').replace('.', '-')
        filename = f"pedido-{pedido_id}-{timestamp}.json"
        filepath = pedido_dir / filename
        
        # Adicionar metadados
        json_data = {
            **pedido_data,
            "savedAt": datetime.utcnow().isoformat(),
            "savedBy": "SGP System",
            "version": "1.0"
        }
        
        # Salvar arquivo JSON
        with filepath.open('w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        # Retornar caminho relativo
        relative_path = filepath.relative_to(MEDIA_ROOT)
        path_str = str(relative_path).replace("\\", "/")
        
        print(f"[UPLOAD] JSON do pedido {pedido_id} salvo em {path_str}")
        
        return {
            "message": "JSON salvo com sucesso",
            "path": path_str,
            "filename": filename
        }
        
    except Exception as e:
        print(f"[ERROR] Erro ao salvar JSON do pedido {pedido_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar JSON: {str(e)}")


@router.post("/", response_model=PedidoResponse)
async def criar_pedido(
    pedido: PedidoCreate,
    session: AsyncSession = Depends(get_session),
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Cria um novo pedido com todos os dados fornecidos.
    Aceita o JSON completo com items, dados do cliente, valores, etc.
    """
    global ULTIMO_PEDIDO_ID
    try:
        # Converter o pedido para dict e preparar para o banco
        pedido_data = pedido.model_dump(exclude_unset=True)
        raw_items = pedido_data.pop('items', [])
        items_payload, pending_uploads, _ = prepare_items_for_storage(raw_items)
        # Normalizar campos obrigatórios
        pedido_data = ensure_pedido_defaults(pedido_data)

        # Converter items para JSON string para armazenar no banco
        items_json = items_to_json_string(items_payload)
        
        # Criar o pedido no banco
        db_pedido = Pedido(
            **pedido_data,
            items=items_json,
            data_criacao=datetime.utcnow(),
            ultima_atualizacao=datetime.utcnow()
        )
        
        session.add(db_pedido)
        await session.flush()

        if await apply_image_changes(session, db_pedido.id, pending_uploads, [], items_payload):
            db_pedido.items = items_to_json_string(items_payload)

        await session.commit()
        await session.refresh(db_pedido)
        
        # Incrementar contador global de pedidos
        ULTIMO_PEDIDO_ID += 1
        
        # Converter de volta para response
        pedido_dict = db_pedido.model_dump()
        cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
        pedido_dict['cidade_cliente'] = cidade
        pedido_dict['estado_cliente'] = estado
        pedido_dict['items'] = json_string_to_items(db_pedido.items or "[]")
        response = PedidoResponse(**pedido_dict)
        
        # Obter informações do usuário atual para incluir no broadcast
        user_info = await get_current_user_from_token(token, session)
        broadcast_order_event("order_created", response, None, user_info)
        
        return response
        
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar pedido: {str(e)}")

def _validate_iso_date(value: Optional[str], field_name: str) -> Optional[str]:
    if not value:
        return None
    try:
        datetime.fromisoformat(value)
        return value
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} inválida: {value}")


@router.get("/", response_model=List[PedidoResponse])
async def listar_pedidos(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: Optional[Status] = Query(default=None),
    cliente: Optional[str] = Query(default=None),
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
):
    """
    Lista todos os pedidos com seus items convertidos de volta para objetos.
    """
    try:
        filters = select(Pedido)
        if status:
            filters = filters.where(Pedido.status == status)

        if cliente:
            search = f"%{cliente.strip().lower()}%"
            filters = filters.where(func.lower(Pedido.cliente).like(search))

        data_inicio = _validate_iso_date(data_inicio, "data_inicio")
        data_fim = _validate_iso_date(data_fim, "data_fim")

        if data_inicio and data_fim and data_inicio > data_fim:
            raise HTTPException(status_code=400, detail="data_inicio deve ser menor ou igual a data_fim")

        if data_inicio:
            filters = filters.where(Pedido.data_entrada >= data_inicio)
        if data_fim:
            filters = filters.where(Pedido.data_entrada <= data_fim)

        filters = filters.order_by(Pedido.data_criacao.desc()).offset(skip).limit(limit)
        result = await session.exec(filters)
        pedidos = result.all()
        
        # Converter items de JSON string para objetos
        response_pedidos = []
        for pedido in pedidos:
            items = json_string_to_items(pedido.items)

            pedido_dict = pedido.model_dump()
            cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
            pedido_dict['cidade_cliente'] = cidade
            pedido_dict['estado_cliente'] = estado
            pedido_dict['items'] = items
            response_pedido = PedidoResponse(**pedido_dict)
            response_pedidos.append(response_pedido)
        
        return response_pedidos
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos: {str(e)}")

@router.get("/{pedido_id}", response_model=PedidoResponse)
async def obter_pedido(pedido_id: int, session: AsyncSession = Depends(get_session)):
    """
    Obtém um pedido específico por ID com seus items convertidos.
    """
    try:
        pedido = await session.get(Pedido, pedido_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # Converter items de JSON string para objetos
        items = json_string_to_items(pedido.items)

        pedido_dict = pedido.model_dump()
        cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
        pedido_dict['cidade_cliente'] = cidade
        pedido_dict['estado_cliente'] = estado
        pedido_dict['items'] = items
        return PedidoResponse(**pedido_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter pedido: {str(e)}")

@router.patch("/{pedido_id}", response_model=PedidoResponse)
async def atualizar_pedido(
    pedido_id: int,
    pedido_update: PedidoUpdate,
    session: AsyncSession = Depends(get_session),
    is_admin: bool = Depends(get_current_user_admin),
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Atualiza um pedido existente. Aceita atualizações parciais.
    Requer permissão de administrador para alterar campo 'financeiro'.
    """
    try:
        db_pedido = await session.get(Pedido, pedido_id)
        if not db_pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
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
        
        # Preparar dados para atualização (exclude_unset=True garante que apenas campos enviados sejam processados)
        update_data = pedido_update.model_dump(exclude_unset=True)
        
        # Verificação de permissão: SOMENTE o campo "financeiro" exige admin
        # Todos os outros campos (expedição, itens, observação, etc.) podem ser editados por qualquer usuário
        if 'financeiro' in update_data and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Somente administradores podem alterar o status financeiro."
            )
        
        # Converter items para JSON string se existirem
        items_payload_for_images: Optional[List[dict[str, Any]]] = None
        pending_uploads: List[PendingImageUpload] = []
        pending_removals: List[PendingImageRemoval] = []
        if 'items' in update_data and update_data['items'] is not None:
            items_payload_for_images, pending_uploads, pending_removals = prepare_items_for_storage(
                update_data['items'],
                allow_removal=True
            )
            update_data['items'] = items_to_json_string(items_payload_for_images)
        
        if 'data_entrega' in update_data and not update_data['data_entrega']:
            # Garantir que data_entrega nunca fique vazia devido à restrição do banco
            update_data['data_entrega'] = db_pedido.data_entrada

        if 'forma_envio_id' in update_data and update_data['forma_envio_id'] is None:
            update_data['forma_envio_id'] = db_pedido.forma_envio_id or 0

        if 'numero' in update_data and not update_data['numero']:
            update_data['numero'] = db_pedido.numero or str(int(datetime.utcnow().timestamp()))

        estado_update = (update_data.pop('estado_cliente', None) or '').strip()
        if 'cidade_cliente' in update_data or estado_update:
            cidade_atual, estado_atual = decode_city_state(db_pedido.cidade_cliente)
            nova_cidade = update_data.get('cidade_cliente', cidade_atual) or ''
            nova_cidade, _ = decode_city_state(nova_cidade)
            estado_final = estado_update if estado_update else estado_atual
            update_data['cidade_cliente'] = encode_city_state(nova_cidade, estado_final)

        # Atualizar timestamp
        update_data['ultima_atualizacao'] = datetime.utcnow()
        
        # Aplicar atualizações
        for field, value in update_data.items():
            setattr(db_pedido, field, value)
        
        session.add(db_pedido)
        if items_payload_for_images is not None:
            if await apply_image_changes(
                session,
                db_pedido.id,
                pending_uploads,
                pending_removals,
                items_payload_for_images
            ):
                db_pedido.items = items_to_json_string(items_payload_for_images)

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
        
        pedido_dict = db_pedido.model_dump()
        cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
        pedido_dict['cidade_cliente'] = cidade
        pedido_dict['estado_cliente'] = estado
        pedido_dict['items'] = items
        response = PedidoResponse(**pedido_dict)
        
        # Obter informações do usuário atual para incluir no broadcast
        user_info = await get_current_user_from_token(token, session)
        
        # 🔥 SEMPRE ENVIAR order_updated quando há qualquer atualização
        if __debug__:
            print(f"[Pedidos] Enviando broadcast 'order_updated' para pedido {pedido_id}")
        broadcast_order_event("order_updated", response, None, user_info)
        
        # 🔥 ENVIAR order_status_updated APENAS quando há mudança real de status
        if status_changed:
            if __debug__:
                print(f"[Pedidos] Enviando broadcast 'order_status_updated' para pedido {pedido_id}")
            broadcast_order_event("order_status_updated", response, None, user_info)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao atualizar pedido: {str(e)}")

@router.delete("/{pedido_id}")
async def deletar_pedido(
    pedido_id: int,
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

        images_result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido_id))
        for image in images_result.all():
            delete_media_file(image.path)
            await session.delete(image)
        
        await session.delete(db_pedido)
        await session.commit()
        broadcast_order_event("order_deleted", order_id=pedido_id)
        return {"message": "Pedido deletado com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar pedido: {str(e)}")

@router.delete("/all")
async def deletar_todos_pedidos(
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
        
        # Deletar imagens de todos os pedidos
        for pedido in all_pedidos:
            images_result = await session.exec(select(PedidoImagem).where(PedidoImagem.pedido_id == pedido.id))
            for image in images_result.all():
                delete_media_file(image.path)
                await session.delete(image)
        
        # Deletar todos os pedidos (os itens serão deletados em cascata)
        for pedido in all_pedidos:
            await session.delete(pedido)
        
        await session.commit()
        broadcast_order_event("order_deleted", order_id=None)
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
        
        # Converter items de JSON string para objetos
        response_pedidos = []
        for pedido in pedidos:
            items = json_string_to_items(pedido.items)

            pedido_dict = pedido.model_dump()
            cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
            pedido_dict['cidade_cliente'] = cidade
            pedido_dict['estado_cliente'] = estado
            pedido_dict['items'] = items
            response_pedido = PedidoResponse(**pedido_dict)
            response_pedidos.append(response_pedido)
        
        return response_pedidos
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar pedidos por status: {str(e)}")

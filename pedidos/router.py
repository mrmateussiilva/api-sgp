from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text, func
from fastapi.encoders import jsonable_encoder
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
)
from .realtime import schedule_broadcast
from datetime import datetime
from typing import Any, List, Optional
import orjson

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

STATE_SEPARATOR = "||"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


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


def broadcast_order_event(event_type: str, pedido: Optional[PedidoResponse] = None, order_id: Optional[int] = None) -> None:
    message: dict[str, Any] = {"type": event_type}
    if pedido is not None:
        message["order"] = jsonable_encoder(pedido)
    if order_id is not None:
        message["order_id"] = order_id
    schedule_broadcast(message)

def normalize_acabamento(acabamento_value: Any) -> Optional[Acabamento]:
    if isinstance(acabamento_value, Acabamento):
        return acabamento_value
    if isinstance(acabamento_value, dict):
        return Acabamento(**acabamento_value)
    return None


def items_to_json_string(items) -> str:
    """Converte lista de items para string JSON"""
    items_data = []
    for item in items:
        if hasattr(item, 'model_dump'):
            # Se for um objeto SQLModel
            item_dict = item.model_dump(exclude_none=True, exclude_unset=True)
            # Converter acabamento para dict
            acabamento = getattr(item, 'acabamento', None)
            if acabamento:
                item_dict['acabamento'] = normalize_acabamento(acabamento).model_dump(exclude_none=True)
        else:
            # Se já for um dict
            item_dict = item.copy()
            # Converter acabamento para dict se existir
            acabamento_value = item_dict.get('acabamento')
            if hasattr(acabamento_value, 'model_dump'):
                item_dict['acabamento'] = acabamento_value.model_dump(exclude_none=True)
            elif isinstance(acabamento_value, dict):
                item_dict['acabamento'] = Acabamento(**acabamento_value).model_dump(exclude_none=True)
        items_data.append(item_dict)
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

@router.post("/", response_model=PedidoResponse)
async def criar_pedido(pedido: PedidoCreate, session: AsyncSession = Depends(get_session)):
    """
    Cria um novo pedido com todos os dados fornecidos.
    Aceita o JSON completo com items, dados do cliente, valores, etc.
    """
    try:
        # Converter o pedido para dict e preparar para o banco
        pedido_data = pedido.model_dump(exclude_unset=True)
        items = pedido_data.pop('items', [])
        # Normalizar campos obrigatórios
        pedido_data = ensure_pedido_defaults(pedido_data)

        # Converter items para JSON string para armazenar no banco
        items_json = items_to_json_string(items)
        
        # Criar o pedido no banco
        db_pedido = Pedido(
            **pedido_data,
            items=items_json,
            data_criacao=datetime.utcnow(),
            ultima_atualizacao=datetime.utcnow()
        )
        
        session.add(db_pedido)
        await session.commit()
        await session.refresh(db_pedido)
        
        # Converter de volta para response
        pedido_dict = db_pedido.model_dump()
        cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
        pedido_dict['cidade_cliente'] = cidade
        pedido_dict['estado_cliente'] = estado
        pedido_dict['items'] = json_string_to_items(db_pedido.items or "[]")
        response = PedidoResponse(**pedido_dict)
        broadcast_order_event("order_created", response)
        return response
        
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
async def atualizar_pedido(pedido_id: int, pedido_update: PedidoUpdate, session: AsyncSession = Depends(get_session)):
    """
    Atualiza um pedido existente. Aceita atualizações parciais.
    """
    try:
        db_pedido = await session.get(Pedido, pedido_id)
        if not db_pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        # Preparar dados para atualização
        update_data = pedido_update.model_dump(exclude_unset=True)
        
        # Converter items para JSON string se existirem
        if 'items' in update_data and update_data['items'] is not None:
            update_data['items'] = items_to_json_string(update_data['items'])
        
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
        await session.commit()
        await session.refresh(db_pedido)
        
        # Converter de volta para response
        items = json_string_to_items(db_pedido.items or "[]")
        
        pedido_dict = db_pedido.model_dump()
        cidade, estado = decode_city_state(pedido_dict.get('cidade_cliente'))
        pedido_dict['cidade_cliente'] = cidade
        pedido_dict['estado_cliente'] = estado
        pedido_dict['items'] = items
        response = PedidoResponse(**pedido_dict)
        broadcast_order_event("order_updated", response)
        if any(key in update_data for key in ["financeiro", "conferencia", "sublimacao", "costura", "expedicao", "pronto", "status"]):
            broadcast_order_event("order_status_updated", response)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao atualizar pedido: {str(e)}")

@router.delete("/{pedido_id}")
async def deletar_pedido(pedido_id: int, session: AsyncSession = Depends(get_session)):
    """
    Deleta um pedido existente.
    """
    try:
        db_pedido = await session.get(Pedido, pedido_id)
        if not db_pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
        await session.delete(db_pedido)
        await session.commit()
        broadcast_order_event("order_deleted", order_id=pedido_id)
        return {"message": "Pedido deletado com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar pedido: {str(e)}")

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

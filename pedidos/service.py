from typing import List, Optional, Any, Dict
import logging
import orjson
from datetime import datetime
from pathlib import Path
import aiofiles
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

from .schema import (
    Pedido, 
    PedidoCreate, 
    PedidoUpdate, 
    PedidoResponse, 
    ItemPedido, 
    Acabamento, 
    Status,
    PedidoImagem
)
from .images import MEDIA_ROOT, absolute_media_path, delete_media_file

logger = logging.getLogger(__name__)

# Separador global (duplicado do router.py por enquanto)
STATE_SEPARATOR = "||"

# --- Helper Functions ---

def normalize_acabamento(acabamento_value: Any) -> Optional[Acabamento]:
    if isinstance(acabamento_value, Acabamento):
        return acabamento_value
    if isinstance(acabamento_value, dict):
        return Acabamento(**acabamento_value)
    return None

def item_to_plain_dict(item: Any) -> Dict[str, Any]:
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

def items_to_json_string(items: List[ItemPedido]) -> str:
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
        logger.error(f"Erro ao converter JSON para items: {e}")
        return []

def normalize_pedido_status(pedido: Pedido) -> None:
    """Normaliza o status de um pedido carregado do banco."""
    if not hasattr(pedido, 'status'):
        return
    
    status_value = pedido.status
    status_map = {
        'pendente': Status.PENDENTE,
        'em producao': Status.EM_PRODUCAO,
        'em produção': Status.EM_PRODUCAO,
        'em_producao': Status.EM_PRODUCAO,
        'pronto': Status.PRONTO,
        'entregue': Status.ENTREGUE,
        'concluido': Status.ENTREGUE,
        'concluído': Status.ENTREGUE,
        'cancelado': Status.CANCELADO,
    }
    
    try:
        if isinstance(status_value, str):
            normalized = status_value.lower().strip()
            object.__setattr__(pedido, 'status', status_map.get(normalized, Status.PENDENTE))
        elif not isinstance(status_value, Status) and status_value is not None:
            object.__setattr__(pedido, 'status', Status.PENDENTE)
    except (ValueError, TypeError, AttributeError):
        object.__setattr__(pedido, 'status', Status.PENDENTE)

def decode_city_state(cidade_com_uf: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Extrai cidade e estado de string 'Cidade - UF'"""
    if not cidade_com_uf:
        return None, None
    parts = cidade_com_uf.rsplit(" - ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return cidade_com_uf, None

def encode_city_state(cidade: str, estado: Optional[str]) -> str:
    """Combina cidade e estado em string 'Cidade || UF' ou similar (depende do separador)"""
    # Usando separador interno para consistência
    separator = STATE_SEPARATOR 
    # Mas wait, o separador no banco é " || " ou " - "?
    # No router.py antigo: STATE_SEPARATOR = "||"
    # No router.py novo: encode_city_state usava STATE_SEPARATOR
    # Mas decode_city_state usa " - "
    
    # Verificando decode_city_state original:
    # if STATE_SEPARATOR in value: ... else split(" - ", 1)
    # Parece confuso. Vamos padronizar.
    
    base_cidade, _ = decode_city_state(cidade)
    base_cidade = base_cidade or cidade # Fallback
    
    estado_normalized = (estado or '').strip()
    if estado_normalized:
        # Se decode usa " - ", talvez devêssemos usar " - " para compatibilidade visual?
        # Ou manter "||" se for usado internamente para separação robusta?
        # O código original usava STATE_SEPARATOR = "||" no encode
        return f"{base_cidade}{separator}{estado_normalized}"
    return base_cidade


def pedido_to_response_dict(pedido: Pedido, items: List[ItemPedido]) -> dict:
    """Converte um objeto Pedido para dicionário para criar PedidoResponse."""
    cidade, estado = decode_city_state(pedido.cidade_cliente)
    
    # Calcular valor_total_calculado (frete + itens) para validação
    # TODO: Evitar import circular se relatorios depender de pedidos
    # Por enquanto, mantendo simples:
    def parse_currency(val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        return float(str(val).replace("R$", "").replace(".", "").replace(",", ".").strip())

    valor_frete_num = parse_currency(pedido.valor_frete) if pedido.valor_frete else 0.0
    valor_itens_num = parse_currency(pedido.valor_itens) if pedido.valor_itens else 0.0
    valor_total_calculado = valor_frete_num + valor_itens_num
    
    return {
        'id': pedido.id,
        'numero': pedido.numero,
        'data_entrada': pedido.data_entrada,
        'data_entrega': pedido.data_entrega,
        'observacao': pedido.observacao,
        'prioridade': pedido.prioridade,
        'status': pedido.status,
        'cliente': pedido.cliente,
        'telefone_cliente': pedido.telefone_cliente,
        'cidade_cliente': cidade,
        'estado_cliente': estado,
        'valor_total': pedido.valor_total,
        'valor_frete': pedido.valor_frete,
        'valor_itens': pedido.valor_itens,
        'tipo_pagamento': pedido.tipo_pagamento,
        'obs_pagamento': pedido.obs_pagamento,
        'forma_envio': pedido.forma_envio,
        'forma_envio_id': pedido.forma_envio_id,
        'financeiro': pedido.financeiro,
        'conferencia': pedido.conferencia,
        'sublimacao': pedido.sublimacao,
        'costura': pedido.costura,
        'expedicao': pedido.expedicao,
        'pronto': pedido.pronto,
        'sublimacao_maquina': pedido.sublimacao_maquina,
        'sublimacao_data_impressao': pedido.sublimacao_data_impressao,
        'items': items,
        'data_criacao': pedido.data_criacao,
        'ultima_atualizacao': pedido.ultima_atualizacao,
        'valor_total_calculado': f"{valor_total_calculado:.2f}".replace('.', ',')
    }

async def _save_pedido_json_internal(pedido_id: int, pedido_data: dict[str, Any]) -> None:
    # Salva JSON do pedido em disco (MEDIA_ROOT/pedidos/{pedido_id}/)
    try:
        pedido_dir = MEDIA_ROOT / "pedidos" / str(pedido_id)
        pedido_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        filename = f"pedido-{pedido_id}-{timestamp}.json"
        filepath = pedido_dir / filename

        json_data: Dict[str, Any] = {
            **pedido_data,
            "savedAt": datetime.utcnow().isoformat(),
            "savedBy": "SGP System",
            "version": "1.0",
        }

        payload = orjson.dumps(json_data, option=orjson.OPT_INDENT_2, default=str)
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(payload)

    except Exception as e:
        logger.warning("Erro ao salvar JSON interno do pedido %s: %s", pedido_id, e, exc_info=True)


class PedidoService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, pedido_id: int) -> Optional[Pedido]:
        return await self.session.get(Pedido, pedido_id)

    async def get_all(
        self, 
        skip: int = 0, 
        limit: int = 50,
        status: Optional[str] = None,
        cliente: Optional[str] = None
    ) -> List[Pedido]:
        query = select(Pedido).offset(skip).limit(limit).order_by(Pedido.data_criacao.desc())
        
        if status:
            query = query.where(Pedido.status == status)
        if cliente:
            query = query.where(Pedido.cliente.ilike(f"%{cliente}%"))
            
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, pedido_create: PedidoCreate) -> Pedido:
        # Prepara items
        items_json = items_to_json_string(pedido_create.items)
        
        # Cria objeto Pedido
        db_pedido = Pedido.model_validate(
            pedido_create, 
            update={"items": items_json}
        )
        
        # Lógica de numeração incremental (simplificada, idealmente deveria ser sequence no banco)
        # TODO: Mover para sequence ou tabela separada para evitar race condition
        
        self.session.add(db_pedido)
        await self.session.commit()
        await self.session.refresh(db_pedido)
        
        # Salva backup JSON
        pedido_dict = pedido_to_response_dict(db_pedido, pedido_create.items)
        await _save_pedido_json_internal(db_pedido.id, pedido_dict)
        
        return db_pedido

    async def update(self, pedido_id: int, pedido_update: PedidoUpdate) -> Pedido:
        db_pedido = await self.get_by_id(pedido_id)
        if not db_pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
            
        pedido_data = pedido_update.model_dump(exclude_unset=True)
        
        # Trata items separadamente
        if "items" in pedido_data:
            items = pedido_data.pop("items")
            db_pedido.items = items_to_json_string(items)
            
        for key, value in pedido_data.items():
            setattr(db_pedido, key, value)
            
        db_pedido.ultima_atualizacao = datetime.utcnow()
        
        self.session.add(db_pedido)
        await self.session.commit()
        await self.session.refresh(db_pedido)
        
        return db_pedido

    async def delete(self, pedido_id: int) -> bool:
        db_pedido = await self.get_by_id(pedido_id)
        if not db_pedido:
            return False
            
        await self.session.delete(db_pedido)
        await self.session.commit()
        
        # Limpar mídia associada (fazer em background idealmente)
        # TODO: Implementar limpeza de mídia
        
        return True
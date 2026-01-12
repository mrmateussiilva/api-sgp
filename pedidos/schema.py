from sqlmodel import SQLModel, Field, Column
from typing import List, Optional
from enum import Enum
from datetime import datetime
from pydantic import ConfigDict, field_validator, model_validator
from sqlalchemy import TypeDecorator, String, Enum as SQLEnum

class Prioridade(str, Enum):
    NORMAL = "NORMAL"
    ALTA = "ALTA"

class Status(str, Enum):
    PENDENTE = "pendente"
    EM_PRODUCAO = "em_producao"
    PRONTO = "pronto"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class StatusType(TypeDecorator):
    """TypeDecorator para normalizar valores de status ao carregar do banco.
    
    Este TypeDecorator intercepta valores do banco antes que o SQLAlchemy tente
    converter para o enum, normalizando strings minúsculas para o enum correto.
    """
    impl = String
    cache_ok = True
    length = 50
    
    def load_dialect_impl(self, dialect):
        """Retorna o tipo de banco subjacente."""
        return dialect.type_descriptor(String(self.length))
    
    def process_result_value(self, value, dialect):
        """Normaliza o valor quando é carregado do banco."""
        if value is None:
            return Status.PENDENTE
        
        # Se já é um enum, retornar diretamente
        if isinstance(value, Status):
            return value
        
        # Se for string, normalizar
        if isinstance(value, str):
            value_lower = value.lower().strip()
            status_map = {
                'pendente': Status.PENDENTE,
                'penden': Status.PENDENTE,
                'em producao': Status.EM_PRODUCAO,
                'em produção': Status.EM_PRODUCAO,
                'em_producao': Status.EM_PRODUCAO,
                'emproducao': Status.EM_PRODUCAO,
                'pronto': Status.PRONTO,
                'entregue': Status.ENTREGUE,
                'concluido': Status.ENTREGUE,
                'concluído': Status.ENTREGUE,
                'cancelado': Status.CANCELADO,
            }
            normalized = status_map.get(value_lower, Status.PENDENTE)
            return normalized
        
        # Fallback
        return Status.PENDENTE
    
    def process_bind_param(self, value, dialect):
        """Normaliza o valor quando é salvo no banco."""
        if value is None:
            return Status.PENDENTE.value
        
        if isinstance(value, Status):
            return value.value
        
        if isinstance(value, str):
            value_lower = value.lower().strip()
            status_map = {
                'pendente': 'pendente',
                'penden': 'pendente',
                'em producao': 'em_producao',
                'em produção': 'em_producao',
                'em_producao': 'em_producao',
                'emproducao': 'em_producao',
                'pronto': 'pronto',
                'entregue': 'entregue',
                'concluido': 'entregue',
                'concluído': 'entregue',
                'cancelado': 'cancelado',
            }
            return status_map.get(value_lower, 'pendente')
        
        return Status.PENDENTE.value


def _normalize_status_value(v):
    """Função auxiliar para normalizar valores de status."""
    if v is None:
        return Status.PENDENTE
    
    # Se já for um enum Status, retornar diretamente
    if isinstance(v, Status):
        return v
    
    # Se for string, normalizar para minúsculas e mapear para o enum
    if isinstance(v, str):
        v_lower = v.lower().strip()
        # Mapear strings variadas para os valores corretos do enum
        status_map = {
            'pendente': 'pendente',
            'penden': 'pendente',
            'em producao': 'em_producao',
            'em produção': 'em_producao',
            'em_producao': 'em_producao',
            'emproducao': 'em_producao',
            'pronto': 'pronto',
            'entregue': 'entregue',
            'concluido': 'entregue',  # "Concluido" mapeia para "entregue"
            'concluído': 'entregue',
            'cancelado': 'cancelado',
        }
        normalized_value = status_map.get(v_lower, 'pendente')
        
        # Converter string para enum usando o valor
        try:
            # Status("pendente") cria o enum usando o valor
            return Status(normalized_value)
        except (ValueError, TypeError):
            # Se não funcionar, buscar manualmente pelo valor
            for status_item in Status:
                if status_item.value == normalized_value:
                    return status_item
            # Fallback: retornar o padrão
            return Status.PENDENTE
    
    return v

class Acabamento(SQLModel):
    overloque: bool = False
    elastico: bool = False
    ilhos: bool = False


class ItemPedido(SQLModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    tipo_producao: Optional[str] = None  # "painel", "totem", "lona", etc.
    descricao: Optional[str] = None
    largura: Optional[str] = None
    altura: Optional[str] = None
    metro_quadrado: Optional[str] = None
    vendedor: Optional[str] = None
    designer: Optional[str] = None
    tecido: Optional[str] = None
    acabamento: Optional[Acabamento] = None
    emenda: Optional[str] = None  # "sem-emenda" ou "com-emenda"
    observacao: Optional[str] = None
    valor_unitario: Optional[str] = None
    imagem: Optional[str] = None
    imagem_path: Optional[str] = None

    # Campos adicionais manipulados pelo frontend
    tipo_acabamento: Optional[str] = None
    quantidade_ilhos: Optional[str] = None
    espaco_ilhos: Optional[str] = None
    valor_ilhos: Optional[str] = None
    ilhos_qtd: Optional[str] = None
    ilhos_valor_unitario: Optional[str] = None
    ilhos_distancia: Optional[str] = None

    quantidade_cordinha: Optional[str] = None
    espaco_cordinha: Optional[str] = None
    valor_cordinha: Optional[str] = None

    quantidade_paineis: Optional[str] = None
    quantidade_totem: Optional[str] = None
    quantidade_lona: Optional[str] = None
    quantidade_adesivo: Optional[str] = None

    valor_totem: Optional[str] = None
    outros_valores_totem: Optional[str] = None
    valor_lona: Optional[str] = None
    outros_valores_lona: Optional[str] = None
    valor_adesivo: Optional[str] = None
    outros_valores_adesivo: Optional[str] = None

    tipo_adesivo: Optional[str] = None
    acabamento_lona: Optional[str] = None
    acabamento_totem: Optional[str] = None
    acabamento_totem_outro: Optional[str] = None

    emenda_qtd: Optional[str] = None
    terceirizado: Optional[bool] = None
    ziper: Optional[bool] = None
    cordinha_extra: Optional[bool] = None
    alcinha: Optional[bool] = None
    toalha_pronta: Optional[bool] = None

    outros_valores: Optional[str] = None


class PedidoBase(SQLModel):
    model_config = ConfigDict(validate_assignment=True)
    
    numero: Optional[str] = Field(default=None, index=True)
    data_entrada: str = Field(index=True)
    data_entrega: Optional[str] = Field(default=None, index=True)
    observacao: Optional[str] = None
    prioridade: Prioridade = Prioridade.NORMAL
    # Usar Status como tipo Python, mas StatusType no SQLAlchemy para normalizar no banco
    # O TypeDecorator converte strings do banco para Status enum automaticamente
    status: Status = Field(
        default=Status.PENDENTE, 
        sa_column=Column(StatusType(length=50), index=True, nullable=False)
    )
    
    @field_validator('status', mode='before')
    @classmethod
    def normalize_status_base(cls, v):
        """Normaliza valores de status na classe base."""
        # O TypeDecorator já deve ter convertido para Status, mas garantimos aqui também
        return _normalize_status_value(v)
    
    def __init__(self, **data):
        # Normalizar status antes de passar para o super().__init__
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = _normalize_status_value(data['status'])
        super().__init__(**data)

    # Dados do cliente
    cliente: str = Field(index=True)
    telefone_cliente: Optional[str] = None
    cidade_cliente: Optional[str] = None

    # Valores
    valor_total: Optional[str] = None
    valor_frete: Optional[str] = None
    valor_itens: Optional[str] = None
    tipo_pagamento: Optional[str] = None
    obs_pagamento: Optional[str] = None

    # Envio
    forma_envio: Optional[str] = None
    forma_envio_id: int = 0

    # Status de produção
    financeiro: bool = False
    conferencia: bool = False
    sublimacao: bool = False
    costura: bool = False
    expedicao: bool = False
    pronto: bool = False
    sublimacao_maquina: Optional[str] = None
    sublimacao_data_impressao: Optional[str] = None


class PedidoCreate(PedidoBase):
    estado_cliente: Optional[str] = None
    items: List[ItemPedido] = Field(default_factory=list)


class PedidoUpdate(SQLModel):
    numero: Optional[str] = None
    data_entrada: Optional[str] = None
    data_entrega: Optional[str] = None
    observacao: Optional[str] = None
    prioridade: Optional[Prioridade] = None
    status: Optional[Status] = None

    # Dados do cliente
    cliente: Optional[str] = None
    telefone_cliente: Optional[str] = None
    cidade_cliente: Optional[str] = None
    estado_cliente: Optional[str] = None

    # Valores
    valor_total: Optional[str] = None
    valor_frete: Optional[str] = None
    valor_itens: Optional[str] = None
    tipo_pagamento: Optional[str] = None
    obs_pagamento: Optional[str] = None

    # Envio
    forma_envio: Optional[str] = None
    forma_envio_id: Optional[int] = None

    # Status de produção
    financeiro: Optional[bool] = None
    conferencia: Optional[bool] = None
    sublimacao: Optional[bool] = None
    costura: Optional[bool] = None
    expedicao: Optional[bool] = None
    pronto: Optional[bool] = None
    sublimacao_maquina: Optional[str] = None
    sublimacao_data_impressao: Optional[str] = None

    # Items
    items: Optional[List[ItemPedido]] = None


class Pedido(PedidoBase, table=True):
    __tablename__ = "pedidos"

    id: Optional[int] = Field(default=None, primary_key=True)
    items: Optional[str] = Field(default=None)  # JSON string
    data_criacao: Optional[datetime] = Field(default_factory=datetime.utcnow)
    ultima_atualizacao: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @model_validator(mode='before')
    @classmethod
    def normalize_status_before(cls, data):
        """Normaliza valores de status antes da validação."""
        if isinstance(data, dict) and 'status' in data:
            data['status'] = _normalize_status_value(data['status'])
        elif hasattr(data, '__dict__'):
            # Se data é um objeto SQLAlchemy/SQLModel já criado
            if hasattr(data, 'status') and isinstance(getattr(data, 'status', None), str):
                setattr(data, 'status', _normalize_status_value(getattr(data, 'status')))
        return data

    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, v):
        """Normaliza valores de status para minúsculas conforme o enum."""
        return _normalize_status_value(v)

    @field_validator('data_criacao', 'ultima_atualizacao', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v
    
    def __setattr__(self, name, value):
        """Intercepta atribuição de status para normalizar."""
        if name == 'status' and isinstance(value, str):
            value = _normalize_status_value(value)
        super().__setattr__(name, value)


class PedidoImagem(SQLModel, table=True):
    __tablename__ = "pedido_imagens"

    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedidos.id", index=True)
    item_index: Optional[int] = Field(default=None, index=True)
    item_identificador: Optional[str] = Field(default=None, index=True)
    filename: str
    mime_type: str
    path: str
    tamanho: int = 0
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class PedidoResponse(PedidoBase):
    id: int
    items: List[ItemPedido]
    data_criacao: datetime
    ultima_atualizacao: datetime
    estado_cliente: Optional[str] = None
    valor_total_calculado: Optional[str] = None  # Campo calculado: frete + itens (para validação)
    
    model_config = ConfigDict(extra="allow")  # Permite campos extras
from sqlmodel import SQLModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime
from pydantic import ConfigDict, field_validator

class Prioridade(str, Enum):
    NORMAL = "NORMAL"
    ALTA = "ALTA"

class Status(str, Enum):
    PENDENTE = "pendente"
    EM_PRODUCAO = "em_producao"
    PRONTO = "pronto"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"

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
    numero: Optional[str] = Field(default=None, index=True)
    data_entrada: str = Field(index=True)
    data_entrega: Optional[str] = Field(default=None, index=True)
    observacao: Optional[str] = None
    prioridade: Prioridade = Prioridade.NORMAL
    status: Status = Field(default=Status.PENDENTE, index=True)

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

    @field_validator('data_criacao', 'ultima_atualizacao', mode='before')
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class PedidoResponse(PedidoBase):
    id: int
    items: List[ItemPedido]
    data_criacao: datetime
    ultima_atualizacao: datetime
    estado_cliente: Optional[str] = None

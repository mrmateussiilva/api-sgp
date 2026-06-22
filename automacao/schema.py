from typing import List, Optional
from sqlmodel import SQLModel


class PedidoMetragemItem(SQLModel):
    pedido_id: int
    numero: Optional[str] = None
    cliente: str
    data_entrada: str
    data_entrega: Optional[str] = None
    status: str
    total_itens: int
    total_metragem: float
    valor_total: float


class PedidoMetragemResponse(SQLModel):
    items: List[PedidoMetragemItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str


class ProducaoTipoEstatisticaItem(SQLModel):
    tipo_producao: str
    total_pedidos: int
    total_itens: int
    total_metragem: float
    valor_total: float


class ProducaoTipoEstatisticaResponse(SQLModel):
    items: List[ProducaoTipoEstatisticaItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str


class ProducaoTecidoEstatisticaItem(SQLModel):
    tecido: str
    total_pedidos: int
    total_itens: int
    total_metragem: float


class ProducaoTecidoEstatisticaResponse(SQLModel):
    items: List[ProducaoTecidoEstatisticaItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str


class AlertaPedidoItem(SQLModel):
    pedido_id: int
    numero: Optional[str] = None
    cliente: str
    data_entrega: Optional[str] = None
    status: str
    tipo_alerta: str  # "atrasado", "urgente_pendente", "estagnado"
    horas_estagnado: Optional[int] = None


class AlertasProducaoResponse(SQLModel):
    items: List[AlertaPedidoItem]


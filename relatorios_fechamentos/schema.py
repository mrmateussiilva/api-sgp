from typing import List, Optional

from sqlmodel import SQLModel


class RelatorioQuantidadeResponse(SQLModel):
    total: int
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    status: Optional[str] = None
    cliente: Optional[str] = None


class RelatorioStatusItem(SQLModel):
    status: str
    total: int


class RelatorioStatusResponse(SQLModel):
    items: List[RelatorioStatusItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    cliente: Optional[str] = None


class RelatorioRankingItem(SQLModel):
    name: str
    pedidos: int
    items: float
    revenue: float


class RelatorioRankingResponse(SQLModel):
    category: str
    items: List[RelatorioRankingItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    status: Optional[str] = None


class RelatorioTrendItem(SQLModel):
    period: str
    pedidos: int
    revenue: float
    frete: float
    servico: float


class RelatorioTrendResponse(SQLModel):
    group_by: str
    items: List[RelatorioTrendItem]
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    status: Optional[str] = None


class RelatorioValorTotalResponse(SQLModel):
    total_pedidos: int
    valor_total: float
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    status: Optional[str] = None
    cliente: Optional[str] = None
    vendedor: Optional[str] = None
    designer: Optional[str] = None

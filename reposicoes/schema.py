from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ReposicaoBase(SQLModel):
    order_id: int = Field(foreign_key="pedidos.id", index=True)
    motivo: str
    descricao: Optional[str] = None
    data_solicitacao: date = Field(default_factory=date.today)
    data_entrega_prevista: Optional[date] = None
    status: str = Field(default="Pendente")
    prioridade: str = Field(default="NORMAL")
    observacao: Optional[str] = None
    financeiro: bool = Field(default=False)
    conferencia: bool = Field(default=False)
    sublimacao: bool = Field(default=False)
    costura: bool = Field(default=False)
    expedicao: bool = Field(default=False)
    pronto: bool = Field(default=False)


class Reposicao(ReposicaoBase, table=True):
    __tablename__ = "reposicoes"

    id: Optional[int] = Field(default=None, primary_key=True)
    numero: Optional[str] = Field(default=None, index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReposicaoCreate(ReposicaoBase):
    pass


class ReposicaoUpdate(SQLModel):
    order_id: Optional[int] = None
    motivo: Optional[str] = None
    descricao: Optional[str] = None
    data_solicitacao: Optional[date] = None
    data_entrega_prevista: Optional[date] = None
    status: Optional[str] = None
    prioridade: Optional[str] = None
    observacao: Optional[str] = None
    financeiro: Optional[bool] = None
    conferencia: Optional[bool] = None
    sublimacao: Optional[bool] = None
    costura: Optional[bool] = None
    expedicao: Optional[bool] = None
    pronto: Optional[bool] = None


class ReposicaoResponse(ReposicaoBase):
    id: int
    numero: Optional[str] = None
    created_at: datetime
    updated_at: datetime

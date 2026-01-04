from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, DateTime, func


class ProducaoBase(SQLModel):
    name: str
    description: Optional[str] = None
    active: bool = Field(default=True)


class Producao(ProducaoBase, table=True):
    __tablename__ = "producoes"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class ProducaoCreate(ProducaoBase):
    pass


class ProducaoUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None


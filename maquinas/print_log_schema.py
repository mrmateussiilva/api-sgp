from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, DateTime, func
from enum import Enum


class PrintLogStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    REPRINT = "reprint"


class PrintLogBase(SQLModel):
    printer_id: int = Field(foreign_key="machines.id", index=True)
    pedido_id: int = Field(foreign_key="pedidos.id", index=True)
    item_id: Optional[int] = None
    status: PrintLogStatus
    error_message: Optional[str] = None


class PrintLog(PrintLogBase, table=True):
    __tablename__ = "print_logs"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class PrintLogCreate(PrintLogBase):
    pass


class PrintLogResponse(PrintLogBase):
    id: int
    printer_name: str
    pedido_numero: Optional[str] = None
    created_at: datetime

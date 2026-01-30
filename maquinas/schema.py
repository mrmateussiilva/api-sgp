from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, DateTime, func


class MachineBase(SQLModel):
    name: str = Field(index=True)
    active: bool = Field(default=True)


class Machine(MachineBase, table=True):
    __tablename__ = "machines"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )


class MachineCreate(MachineBase):
    pass


class MachineUpdate(SQLModel):
    name: Optional[str] = None
    active: Optional[bool] = None


class MachineDashboardItem(SQLModel):
    order_id: int
    order_number: Optional[str] = None
    item_index: int
    item_name: Optional[str] = None # descricao ou tipo_producao
    dimensions: Optional[str] = None # largura x altura
    material: Optional[str] = None # tecido ou lona
    date_due: Optional[str] = None
    preview_url: Optional[str] = None
    status: str
    priority: str 


class MachineDashboardData(SQLModel):
    machine_id: int
    machine_name: str
    total_items: int
    total_area: float
    queue: list[MachineDashboardItem]

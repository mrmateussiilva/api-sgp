from typing import Optional

from sqlmodel import SQLModel


class RelatorioQuantidadeResponse(SQLModel):
    total: int
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    date_mode: str
    status: Optional[str] = None
    cliente: Optional[str] = None

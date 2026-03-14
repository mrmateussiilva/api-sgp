from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class SafiraLog(SQLModel, table=True):
    __tablename__ = "safira_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    pergunta: str
    intent_detectada: str
    reconhecida: bool
    usuario_id: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

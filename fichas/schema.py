"""
Schemas Pydantic para Fichas.
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from pydantic import ConfigDict, field_validator


class FichaBase(SQLModel):
    """Campos base da ficha."""
    client_id: Optional[int] = None
    nome: Optional[str] = None
    descricao: Optional[str] = None
    # Outros campos podem ser adicionados aqui conforme necessário


class FichaCreate(FichaBase):
    """Schema para criação de ficha."""
    imagem_base64: Optional[str] = None


class FichaUpdate(SQLModel):
    """Schema para atualização de ficha."""
    client_id: Optional[int] = None
    nome: Optional[str] = None
    descricao: Optional[str] = None
    imagem_base64: Optional[str] = None


class Ficha(FichaBase, table=True):
    """Modelo SQLModel para tabela de fichas."""
    __tablename__ = "fichas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    imagem_path: Optional[str] = None  # Caminho relativo da imagem
    data_criacao: Optional[datetime] = Field(default_factory=datetime.utcnow)
    ultima_atualizacao: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    @field_validator('data_criacao', 'ultima_atualizacao', mode='before')
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class FichaResponse(FichaBase):
    """Schema de resposta da ficha."""
    id: int
    imagem_path: Optional[str] = None
    data_criacao: datetime
    ultima_atualizacao: datetime


"""
Schemas Pydantic para Fichas.
"""

from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import Optional, Any, Literal
from datetime import datetime
from pydantic import ConfigDict, field_validator, BaseModel


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
    imagem_url: Optional[str] = None  # URL completa para acessar a imagem
    data_criacao: datetime
    ultima_atualizacao: datetime


TemplateType = Literal["geral", "resumo"]


class TemplateTypeEnum(str, Enum):
    """Enum para tipos de template no banco de dados."""
    geral = "geral"
    resumo = "resumo"


class FichaTemplateModel(SQLModel, table=True):
    """Tabela para armazenar templates de ficha."""
    __tablename__ = "ficha_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    template_type: TemplateTypeEnum = Field(index=True, unique=True)
    title: str
    width: float
    height: float
    marginTop: float
    marginBottom: float
    marginLeft: float
    marginRight: float
    fields: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False)
    )
    updatedAt: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class TemplateFieldPayload(BaseModel):
    id: str
    type: str
    label: str
    key: str
    x: float
    y: float
    width: float
    height: float
    fontSize: Optional[float] = None
    bold: Optional[bool] = None
    visible: Optional[bool] = True
    editable: Optional[bool] = True
    imageUrl: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class FichaTemplateData(BaseModel):
    title: str
    width: float
    height: float
    marginTop: float
    marginBottom: float
    marginLeft: float
    marginRight: float
    fields: list[TemplateFieldPayload]

    model_config = ConfigDict(extra="ignore")


class FichaTemplateResponse(FichaTemplateData):
    templateType: TemplateType
    updatedAt: datetime


class FichaTemplatesConfig(BaseModel):
    geral: FichaTemplateData
    resumo: FichaTemplateData


class FichaTemplatesResponse(BaseModel):
    geral: FichaTemplateResponse
    resumo: FichaTemplateResponse


class FichaTemplatesUpdate(BaseModel):
    geral: FichaTemplateData
    resumo: FichaTemplateData

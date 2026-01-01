"""
Schemas Pydantic para Templates de Relatórios.
"""

from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from typing import Optional, Any, Literal, Dict
from datetime import datetime
from pydantic import ConfigDict, BaseModel


RelatorioTemplateType = Literal["envios", "fechamentos"]


class RelatorioTemplateTypeEnum(str, Enum):
    """Enum para tipos de template de relatório no banco de dados."""
    envios = "envios"
    fechamentos = "fechamentos"


class RelatorioTemplateModel(SQLModel, table=True):
    """Tabela para armazenar templates de relatórios."""
    __tablename__ = "relatorio_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    template_type: RelatorioTemplateTypeEnum = Field(index=True, unique=True)
    title: str
    headerFields: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    styles: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False)
    )
    tableConfig: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True)
    )
    pageConfig: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True)
    )
    updatedAt: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class RelatorioTemplateData(BaseModel):
    """Schema de dados do template de relatório."""
    title: str
    headerFields: Dict[str, Optional[str]] = Field(default_factory=dict)
    styles: Dict[str, Any] = Field(default_factory=dict)
    tableConfig: Optional[Dict[str, Any]] = Field(default_factory=dict)
    pageConfig: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class RelatorioTemplateResponse(RelatorioTemplateData):
    """Schema de resposta do template."""
    updatedAt: Optional[datetime] = None


class RelatorioTemplatesConfig(BaseModel):
    """Schema completo com ambos os templates."""
    envios: RelatorioTemplateData
    fechamentos: RelatorioTemplateData


class RelatorioTemplatesResponse(BaseModel):
    """Schema de resposta com ambos os templates."""
    envios: RelatorioTemplateResponse
    fechamentos: RelatorioTemplateResponse


class RelatorioTemplatesUpdate(BaseModel):
    """Schema para atualização dos templates."""
    envios: RelatorioTemplateData
    fechamentos: RelatorioTemplateData


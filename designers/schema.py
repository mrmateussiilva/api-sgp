from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class DesignerBase(SQLModel):
    nome: str
    email: Optional[str] = None
    telefone: Optional[str] = None
    ativo: bool = True
    observacao: Optional[str] = None


class Designer(DesignerBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)


class DesignerCreate(DesignerBase):
    pass


class DesignerUpdate(SQLModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    ativo: Optional[bool] = None
    observacao: Optional[str] = None


# --- Schemas do Painel de Designers ---

class ComentarioResponse(BaseModel):
    id: str
    autor: str
    texto: str
    data: str


class DesignerArteItemResponse(BaseModel):
    """Item de arte retornado pelo painel de designers."""
    item_id: int
    order_id: int
    numero_pedido: str
    cliente: str
    data_entrega: Optional[str] = None
    tipo_producao: Optional[str] = None
    descricao: Optional[str] = None
    largura: Optional[str] = None
    altura: Optional[str] = None
    metro_quadrado: Optional[str] = None
    imagem: Optional[str] = None
    observacao: Optional[str] = None
    status_pedido: str
    prioridade: Optional[str] = None
    status_arte: Literal["aguardando", "liberado"] = "aguardando"

    # Campos técnicos de produção (sem valores monetários)
    tecido: Optional[str] = None
    composicao_tecidos: Optional[str] = None
    acabamento: Optional[dict] = None  # {overloque: bool, elastico: bool, ilhos: bool}
    vendedor: Optional[str] = None
    emenda: Optional[str] = None
    emenda_qtd: Optional[str] = None
    
    # Quantidades específicas
    quantidade_paineis: Optional[str] = None
    quantidade_totem: Optional[str] = None
    quantidade_lona: Optional[str] = None
    quantidade_adesivo: Optional[str] = None
    
    # Detalhes de acabamento
    tipo_acabamento: Optional[str] = None
    quantidade_ilhos: Optional[str] = None
    espaco_ilhos: Optional[str] = None
    quantidade_cordinha: Optional[str] = None
    espaco_cordinha: Optional[str] = None
    
    # Campos específicos por tipo
    tipo_adesivo: Optional[str] = None
    acabamento_lona: Optional[str] = None
    acabamento_totem: Optional[str] = None
    acabamento_totem_outro: Optional[str] = None
    
    # Flags técnicas
    terceirizado: Optional[bool] = None
    ziper: Optional[bool] = None
    cordinha_extra: Optional[bool] = None
    alcinha: Optional[bool] = None
    toalha_pronta: Optional[bool] = None

    # Comentários estilo Trello
    comentarios: List[ComentarioResponse] = []


class PatchStatusArteRequest(BaseModel):
    """Request para atualizar APENAS o status de arte de um item.
    Nunca sobrescreve outros campos do item (quantidade, preço, vendedor, etc.).
    """
    legenda_imagem: Literal["LIBERADO", "AGUARDANDO"]


class PostComentarioRequest(BaseModel):
    """Request para adicionar um novo comentário a um item."""
    texto: str
    autor: str

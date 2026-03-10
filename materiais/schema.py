from typing import Optional, Literal

from sqlmodel import Field, SQLModel


class MaterialBase(SQLModel):
    nome: str
    tipo: str
    valor_metro: float = 0.0
    estoque_metros: float = 0.0
    ativo: bool = True
    observacao: Optional[str] = None


class Material(MaterialBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, index=True)


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(SQLModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    valor_metro: Optional[float] = None
    estoque_metros: Optional[float] = None
    ativo: Optional[bool] = None
    observacao: Optional[str] = None


class MaterialUsoItem(SQLModel):
    material_id: Optional[int] = None
    nome_material: str
    cadastrado: bool = True
    ativo: Optional[bool] = None
    quantidade_usos: int = 0
    percentual_uso: float = 0.0


class MaterialUsoEstatisticasResponse(SQLModel):
    ordem: Literal["mais", "menos"] = "mais"
    total_pedidos_analisados: int = 0
    total_itens_com_material: int = 0
    total_materiais_distintos_com_uso: int = 0
    materiais: list[MaterialUsoItem] = []

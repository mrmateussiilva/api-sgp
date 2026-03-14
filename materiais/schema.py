from typing import Optional, Literal, List, Dict

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


class RankingItem(SQLModel):
    nome: str
    quantidade_itens: int
    area_total_m2: float
    percentual_area: float


class MaterialStatsKPIs(SQLModel):
    total_itens: int
    total_area_m2: float
    material_mais_usado: Optional[str] = None
    acabamento_mais_usado: Optional[str] = None
    total_ilhos: int
    total_itens_com_ilhos: int
    data_pico: Optional[str] = None
    m2_pico: float = 0.0


class MaterialStatsResponse(SQLModel):
    kpis: MaterialStatsKPIs
    ranking_materiais: List[RankingItem]
    ranking_acabamentos: List[RankingItem]
    por_tipo_producao: Dict[str, List[RankingItem]]


class MaterialEvolutionItem(SQLModel):
    data: str
    total: float
    top_materiais: Dict[str, float]


class MaterialEvolutionResponse(SQLModel):
    top_3_nomes: List[str]
    evolucao: List[MaterialEvolutionItem]

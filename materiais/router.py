from collections import Counter
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.schema import Pedido, Status
from pedidos.service import json_string_to_items
from .schema import (
    Material,
    MaterialCreate,
    MaterialUpdate,
    MaterialUsoEstatisticasResponse,
    MaterialUsoItem,
    MaterialStatsResponse,
    MaterialEvolutionResponse,
)
from .stats_service import get_material_stats, get_material_evolution

router = APIRouter(prefix="/materiais", tags=["Materiais"])


@router.get("/", response_model=list[Material])
async def list_materiais(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Material))
    return result.all()


@router.get("/stats", response_model=MaterialStatsResponse)
async def get_materiais_stats_v2(
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    tipo_producao: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Novo endpoint de estatísticas consolidadas para a tela de análise de materiais.
    """
    return await get_material_stats(
        session=session,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo_producao=tipo_producao
    )


@router.get("/stats/evolucao", response_model=MaterialEvolutionResponse)
async def get_materiais_stats_evolucao(
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    tipo_producao: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint para gráfico de evolução de consumo (m²) ao longo do tempo.
    """
    return await get_material_evolution(
        session=session,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo_producao=tipo_producao
    )


def _normalize_material_name(nome: str) -> str:
    return " ".join(nome.strip().casefold().split())


@router.get("/estatisticas/uso", response_model=MaterialUsoEstatisticasResponse)
async def get_estatisticas_uso_materiais(
    limit: int = Query(default=10, ge=1, le=200),
    ordem: Literal["mais", "menos"] = Query(default="mais"),
    incluir_sem_uso: bool = Query(default=False),
    somente_ativos: bool = Query(default=True),
    incluir_cancelados: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    materiais_query = select(Material)
    if somente_ativos:
        materiais_query = materiais_query.where(Material.ativo == True)  # noqa: E712
    materiais_result = await session.exec(materiais_query)
    materiais = materiais_result.all()

    catalogo_por_nome: dict[str, Material] = {}
    for material in materiais:
        catalogo_por_nome[_normalize_material_name(material.nome)] = material

    pedidos_query = select(Pedido)
    if not incluir_cancelados:
        pedidos_query = pedidos_query.where(Pedido.status != Status.CANCELADO)
    pedidos_result = await session.exec(pedidos_query)
    pedidos = pedidos_result.all()

    usos_por_nome: Counter[str] = Counter()
    nomes_exibicao: dict[str, str] = {}
    total_itens_com_material = 0

    for pedido in pedidos:
        for item in json_string_to_items(pedido.items):
            if not item.tecido:
                continue

            nome = item.tecido.strip()
            if not nome:
                continue

            nome_normalizado = _normalize_material_name(nome)
            if not nome_normalizado:
                continue

            usos_por_nome[nome_normalizado] += 1
            total_itens_com_material += 1

            if nome_normalizado not in nomes_exibicao:
                nomes_exibicao[nome_normalizado] = nome

    if incluir_sem_uso:
        for nome_normalizado in catalogo_por_nome:
            usos_por_nome.setdefault(nome_normalizado, 0)

    total_materiais_distintos_com_uso = sum(
        1 for usos in usos_por_nome.values() if usos > 0
    )
    divisor_percentual = total_itens_com_material or 1

    materiais_uso: list[MaterialUsoItem] = []
    for nome_normalizado, quantidade_usos in usos_por_nome.items():
        if quantidade_usos == 0 and not incluir_sem_uso:
            continue

        material_cadastrado = catalogo_por_nome.get(nome_normalizado)
        nome_exibicao = (
            material_cadastrado.nome
            if material_cadastrado
            else nomes_exibicao.get(nome_normalizado, nome_normalizado)
        )

        percentual = round((quantidade_usos / divisor_percentual) * 100, 2)
        materiais_uso.append(
            MaterialUsoItem(
                material_id=material_cadastrado.id if material_cadastrado else None,
                nome_material=nome_exibicao,
                cadastrado=material_cadastrado is not None,
                ativo=material_cadastrado.ativo if material_cadastrado else None,
                quantidade_usos=quantidade_usos,
                percentual_uso=percentual,
            )
        )

    if ordem == "mais":
        materiais_uso.sort(key=lambda item: (-item.quantidade_usos, item.nome_material.casefold()))
    else:
        materiais_uso.sort(key=lambda item: (item.quantidade_usos, item.nome_material.casefold()))

    return MaterialUsoEstatisticasResponse(
        ordem=ordem,
        total_pedidos_analisados=len(pedidos),
        total_itens_com_material=total_itens_com_material,
        total_materiais_distintos_com_uso=total_materiais_distintos_com_uso,
        materiais=materiais_uso[:limit],
    )


@router.get("/{material_id}", response_model=Material)
async def get_material(material_id: int, session: AsyncSession = Depends(get_session)):
    material = await session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado")
    return material


@router.post("/", response_model=Material, status_code=status.HTTP_201_CREATED)
async def create_material(material: MaterialCreate, session: AsyncSession = Depends(get_session)):
    db_material = Material(**material.model_dump())
    session.add(db_material)
    await session.commit()
    await session.refresh(db_material)
    return db_material


@router.patch("/{material_id}", response_model=Material)
async def update_material(
    material_id: int,
    material_update: MaterialUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_material = await session.get(Material, material_id)
    if not db_material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado")

    update_data = material_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_material, field, value)

    session.add(db_material)
    await session.commit()
    await session.refresh(db_material)
    return db_material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: int, session: AsyncSession = Depends(get_session)):
    db_material = await session.get(Material, material_id)
    if not db_material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material não encontrado")

    await session.delete(db_material)
    await session.commit()
    return None

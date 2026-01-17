from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from auth.router import get_current_user
from base import get_session
from pedidos.schema import Pedido
from .schema import Reposicao, ReposicaoCreate, ReposicaoUpdate, ReposicaoResponse

router = APIRouter(prefix="/reposicoes", tags=["Reposicoes"])

STATUS_VALIDOS = {"Pendente", "Em Processamento", "Concluída", "Cancelada"}
PRIORIDADES_VALIDAS = {"NORMAL", "ALTA"}


def _validar_status(status_value: Optional[str]) -> None:
    if status_value is None:
        return
    if status_value not in STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail="Status inválido")


def _validar_prioridade(prioridade_value: Optional[str]) -> None:
    if prioridade_value is None:
        return
    if prioridade_value not in PRIORIDADES_VALIDAS:
        raise HTTPException(status_code=400, detail="Prioridade inválida")


@router.post("/", response_model=ReposicaoResponse, status_code=status.HTTP_201_CREATED)
async def create_reposicao(
    reposicao: ReposicaoCreate,
    session: AsyncSession = Depends(get_session),
    _current_user: dict = Depends(get_current_user),
):
    pedido = await session.get(Pedido, reposicao.order_id)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    _validar_status(reposicao.status)
    _validar_prioridade(reposicao.prioridade)

    db_reposicao = Reposicao(**reposicao.model_dump())
    session.add(db_reposicao)

    try:
        await session.flush()
        db_reposicao.numero = f"REP-{db_reposicao.id}"
        db_reposicao.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(db_reposicao)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Erro ao criar reposição")

    return db_reposicao


@router.get("/", response_model=list[ReposicaoResponse])
async def list_reposicoes(
    order_id: Optional[int] = Query(default=None),
    status_value: Optional[str] = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
    _current_user: dict = Depends(get_current_user),
):
    _validar_status(status_value)

    statement = select(Reposicao)
    if order_id is not None:
        statement = statement.where(Reposicao.order_id == order_id)
    if status_value is not None:
        statement = statement.where(Reposicao.status == status_value)

    statement = statement.order_by(Reposicao.created_at.desc())
    result = await session.exec(statement)
    return result.all()


@router.get("/{reposicao_id}", response_model=ReposicaoResponse)
async def get_reposicao(
    reposicao_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: dict = Depends(get_current_user),
):
    reposicao = await session.get(Reposicao, reposicao_id)
    if not reposicao:
        raise HTTPException(status_code=404, detail="Reposição não encontrada")
    return reposicao


@router.patch("/{reposicao_id}", response_model=ReposicaoResponse)
async def update_reposicao(
    reposicao_id: int,
    reposicao_update: ReposicaoUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: dict = Depends(get_current_user),
):
    reposicao = await session.get(Reposicao, reposicao_id)
    if not reposicao:
        raise HTTPException(status_code=404, detail="Reposição não encontrada")

    if reposicao_update.order_id is not None:
        pedido = await session.get(Pedido, reposicao_update.order_id)
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

    _validar_status(reposicao_update.status)
    _validar_prioridade(reposicao_update.prioridade)

    reposicao_data = reposicao_update.model_dump(exclude_unset=True)
    for field, value in reposicao_data.items():
        setattr(reposicao, field, value)

    reposicao.updated_at = datetime.utcnow()

    session.add(reposicao)
    try:
        await session.commit()
        await session.refresh(reposicao)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Erro ao atualizar reposição")

    return reposicao


@router.delete("/{reposicao_id}")
async def delete_reposicao(
    reposicao_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: dict = Depends(get_current_user),
):
    reposicao = await session.get(Reposicao, reposicao_id)
    if not reposicao:
        raise HTTPException(status_code=404, detail="Reposição não encontrada")

    await session.delete(reposicao)
    await session.commit()
    return {"message": "Reposição excluída com sucesso"}

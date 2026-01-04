from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Producao, ProducaoCreate, ProducaoUpdate

router = APIRouter(prefix="/producoes", tags=["Tipos de Produção"])


@router.get("/", response_model=list[Producao])
async def list_producoes(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Producao))
    return result.all()


@router.get("/ativos", response_model=list[Producao])
async def list_producoes_ativos(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Producao).where(Producao.active.is_(True)))
    return result.all()


@router.get("/{producao_id}", response_model=Producao)
async def get_producao(producao_id: int, session: AsyncSession = Depends(get_session)):
    producao = await session.get(Producao, producao_id)
    if not producao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de produção não encontrado")
    return producao


@router.post("/", response_model=Producao, status_code=status.HTTP_201_CREATED)
async def create_producao(producao: ProducaoCreate, session: AsyncSession = Depends(get_session)):
    db_producao = Producao(**producao.model_dump())
    session.add(db_producao)
    await session.commit()
    await session.refresh(db_producao)
    return db_producao


@router.patch("/{producao_id}", response_model=Producao)
async def update_producao(
    producao_id: int,
    producao_update: ProducaoUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_producao = await session.get(Producao, producao_id)
    if not db_producao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de produção não encontrado")

    update_data = producao_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_producao, field, value)

    session.add(db_producao)
    await session.commit()
    await session.refresh(db_producao)
    return db_producao


@router.delete("/{producao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_producao(producao_id: int, session: AsyncSession = Depends(get_session)):
    db_producao = await session.get(Producao, producao_id)
    if not db_producao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de produção não encontrado")

    await session.delete(db_producao)
    await session.commit()
    return None


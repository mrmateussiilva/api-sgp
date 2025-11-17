from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Vendedor, VendedorCreate, VendedorUpdate

router = APIRouter(prefix="/vendedores", tags=["Vendedores"])


@router.get("/", response_model=list[Vendedor])
async def list_vendedores(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Vendedor))
    return result.all()


@router.get("/ativos", response_model=list[Vendedor])
async def list_vendedores_ativos(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Vendedor).where(Vendedor.ativo.is_(True)))
    return result.all()


@router.get("/{vendedor_id}", response_model=Vendedor)
async def get_vendedor(vendedor_id: int, session: AsyncSession = Depends(get_session)):
    vendedor = await session.get(Vendedor, vendedor_id)
    if not vendedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendedor não encontrado")
    return vendedor


@router.post("/", response_model=Vendedor, status_code=status.HTTP_201_CREATED)
async def create_vendedor(vendedor: VendedorCreate, session: AsyncSession = Depends(get_session)):
    db_vendedor = Vendedor(**vendedor.model_dump())
    session.add(db_vendedor)
    await session.commit()
    await session.refresh(db_vendedor)
    return db_vendedor


@router.patch("/{vendedor_id}", response_model=Vendedor)
async def update_vendedor(
    vendedor_id: int,
    vendedor_update: VendedorUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_vendedor = await session.get(Vendedor, vendedor_id)
    if not db_vendedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendedor não encontrado")

    update_data = vendedor_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_vendedor, field, value)

    session.add(db_vendedor)
    await session.commit()
    await session.refresh(db_vendedor)
    return db_vendedor


@router.delete("/{vendedor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendedor(vendedor_id: int, session: AsyncSession = Depends(get_session)):
    db_vendedor = await session.get(Vendedor, vendedor_id)
    if not db_vendedor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendedor não encontrado")

    await session.delete(db_vendedor)
    await session.commit()
    return None

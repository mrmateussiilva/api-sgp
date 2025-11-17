from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Envio, EnvioCreate, EnvioUpdate

router = APIRouter(prefix="/tipos-envios", tags=["Tipos de Envios"])


@router.get("/", response_model=list[Envio])
async def list_envios(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Envio))
    return result.all()


@router.get("/ativos", response_model=list[Envio])
async def list_envios_ativos(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Envio).where(Envio.ativo.is_(True)))
    return result.all()


@router.get("/{envio_id}", response_model=Envio)
async def get_envio(envio_id: int, session: AsyncSession = Depends(get_session)):
    envio = await session.get(Envio, envio_id)
    if not envio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de envio não encontrado")
    return envio


@router.post("/", response_model=Envio, status_code=status.HTTP_201_CREATED)
async def create_envio(envio: EnvioCreate, session: AsyncSession = Depends(get_session)):
    db_envio = Envio(**envio.model_dump())
    session.add(db_envio)
    await session.commit()
    await session.refresh(db_envio)
    return db_envio


@router.patch("/{envio_id}", response_model=Envio)
async def update_envio(envio_id: int, envio_update: EnvioUpdate, session: AsyncSession = Depends(get_session)):
    db_envio = await session.get(Envio, envio_id)
    if not db_envio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de envio não encontrado")

    envio_data = envio_update.model_dump(exclude_unset=True)
    for field, value in envio_data.items():
        setattr(db_envio, field, value)

    session.add(db_envio)
    await session.commit()
    await session.refresh(db_envio)
    return db_envio


@router.delete("/{envio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_envio(envio_id: int, session: AsyncSession = Depends(get_session)):
    db_envio = await session.get(Envio, envio_id)
    if not db_envio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de envio não encontrado")

    await session.delete(db_envio)
    await session.commit()
    return None

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Cliente, ClienteCreate, ClienteUpdate

router = APIRouter(prefix='/clientes', tags=["Clientes"])


@router.post("/", response_model=Cliente)
async def create_cliente(cliente: ClienteCreate, session: AsyncSession = Depends(get_session)):
    db_cliente = Cliente(**cliente.model_dump())
    session.add(db_cliente)
    await session.commit()
    await session.refresh(db_cliente)
    return db_cliente


@router.get("/", response_model=list[Cliente])
async def read_clientes(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Cliente))
    return result.all()


@router.get("/{cliente_id}", response_model=Cliente)
async def read_cliente(cliente_id: int, session: AsyncSession = Depends(get_session)):
    cliente = await session.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente


@router.patch("/{cliente_id}", response_model=Cliente)
async def update_cliente(cliente_id: int, cliente_update: ClienteUpdate, session: AsyncSession = Depends(get_session)):
    db_cliente = await session.get(Cliente, cliente_id)
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    cliente_data = cliente_update.model_dump(exclude_unset=True)
    for field, value in cliente_data.items():
        setattr(db_cliente, field, value)

    session.add(db_cliente)
    await session.commit()
    await session.refresh(db_cliente)
    return db_cliente


@router.delete("/{cliente_id}")
async def delete_cliente(cliente_id: int, session: AsyncSession = Depends(get_session)):
    db_cliente = await session.get(Cliente, cliente_id)
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    await session.delete(db_cliente)
    await session.commit()
    return {"message": "Cliente deletado com sucesso"}

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Material, MaterialCreate, MaterialUpdate

router = APIRouter(prefix="/materiais", tags=["Materiais"])


@router.get("/", response_model=list[Material])
async def list_materiais(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Material))
    return result.all()


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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Designer, DesignerCreate, DesignerUpdate

router = APIRouter(prefix="/designers", tags=["Designers"])


@router.get("/", response_model=list[Designer])
async def list_designers(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Designer))
    return result.all()


@router.get("/{designer_id}", response_model=Designer)
async def get_designer(designer_id: int, session: AsyncSession = Depends(get_session)):
    designer = await session.get(Designer, designer_id)
    if not designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")
    return designer


@router.post("/", response_model=Designer, status_code=status.HTTP_201_CREATED)
async def create_designer(designer: DesignerCreate, session: AsyncSession = Depends(get_session)):
    db_designer = Designer(**designer.model_dump())
    session.add(db_designer)
    await session.commit()
    await session.refresh(db_designer)
    return db_designer


@router.patch("/{designer_id}", response_model=Designer)
async def update_designer(
    designer_id: int,
    designer_update: DesignerUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_designer = await session.get(Designer, designer_id)
    if not db_designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")

    update_data = designer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_designer, field, value)

    session.add(db_designer)
    await session.commit()
    await session.refresh(db_designer)
    return db_designer


@router.delete("/{designer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_designer(designer_id: int, session: AsyncSession = Depends(get_session)):
    db_designer = await session.get(Designer, designer_id)
    if not db_designer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Designer não encontrado")

    await session.delete(db_designer)
    await session.commit()
    return None

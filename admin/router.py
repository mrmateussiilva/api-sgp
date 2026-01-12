from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from auth.models import User
from base import get_session
from .schema import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin),
        is_active=bool(user.is_active),
    )


@router.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.username == user.username))
    existing = result.first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de usuário já está em uso")

    if len(user.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 8 caracteres")

    now = datetime.now(timezone.utc)
    db_user = User(
        username=user.username,
        password_hash=_hash_password(user.password),
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=now,
        updated_at=now,
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return _to_user_response(db_user)


@router.get("/users/", response_model=list[UserResponse])
async def get_all_users(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User))
    return [_to_user_response(user) for user in result.all()]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return _to_user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, session: AsyncSession = Depends(get_session)):
    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if user_update.username and user_update.username != db_user.username:
        result = await session.exec(select(User).where(User.username == user_update.username))
        existing = result.first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de usuário já está em uso")
        db_user.username = user_update.username

    if user_update.password:
        if len(user_update.password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 8 caracteres")
        db_user.password_hash = _hash_password(user_update.password)

    if user_update.is_admin is not None:
        db_user.is_admin = user_update.is_admin

    if user_update.is_active is not None:
        db_user.is_active = user_update.is_active

    db_user.updated_at = datetime.now(timezone.utc)

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return _to_user_response(db_user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    await session.delete(db_user)
    await session.commit()
    return {"message": "Usuário deletado com sucesso"}

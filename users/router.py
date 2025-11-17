from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from auth.models import User
from base import get_session
from .schema import UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/users", tags=["Usuários"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _to_read_model(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        is_admin=bool(user.is_admin),
        is_active=bool(user.is_active),
        created_at=user.created_at,
    )


@router.get("/", response_model=list[UserRead])
async def list_users(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User))
    return [_to_read_model(user) for user in result.all()]


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return _to_read_model(user)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.username == payload.username))
    existing = result.first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de usuário já está em uso")

    if not payload.password or len(payload.password) < 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 4 caracteres")

    now = datetime.now(timezone.utc)
    user = User(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        is_admin=payload.is_admin,
        is_active=payload.is_active,
        created_at=now,
        updated_at=now,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_read_model(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: int, payload: UserUpdate, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if payload.username and payload.username != user.username:
        result = await session.exec(select(User).where(User.username == payload.username))
        existing = result.first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de usuário já está em uso")
        user.username = payload.username

    if payload.password:
        if len(payload.password) < 4:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha deve ter ao menos 4 caracteres")
        user.password_hash = _hash_password(payload.password)

    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    if payload.is_active is not None:
        user.is_active = payload.is_active

    user.updated_at = datetime.now(timezone.utc)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _to_read_model(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    await session.delete(user)
    await session.commit()
    return None

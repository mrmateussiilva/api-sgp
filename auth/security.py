"""
Funções utilitárias de segurança compartilhadas entre módulos.
"""
from typing import Optional

from jose import JWTError, jwt
from sqlmodel.ext.asyncio.session import AsyncSession

from auth.models import User
from config import settings
from database.database import async_session_maker


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica um token JWT e retorna o payload bruto."""
    if not token:
        return None
    try:
        return jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


async def _load_user(session: AsyncSession, user_id: int) -> Optional[User]:
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


async def get_user_from_token(token: Optional[str], session: Optional[AsyncSession] = None) -> Optional[User]:
    """Retorna o usuário associado ao token, se for válido."""
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    if session is not None:
        return await _load_user(session, user_id)

    async with async_session_maker() as new_session:
        return await _load_user(new_session, user_id)


def extract_bearer_token(header_value: Optional[str]) -> Optional[str]:
    """Extrai token Bearer de um header Authorization."""
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()

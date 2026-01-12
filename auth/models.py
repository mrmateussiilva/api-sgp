from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone


class User(SQLModel, table=True):
    """Modelo de usuário para autenticação"""

    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevokedToken(SQLModel, table=True):
    """Modelo para tokens revogados (persistência de logout)"""

    __tablename__ = "revoked_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    revoked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(SQLModel):
    """Schema para criar usuário"""
    username: str
    password: str
    is_admin: bool = False


class UserResponse(SQLModel):
    """Schema para resposta de usuário (sem senha)"""
    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: Optional[datetime] = None

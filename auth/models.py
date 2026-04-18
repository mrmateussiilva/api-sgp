from sqlmodel import SQLModel, Field, Column
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class FlexibleDateTime(TypeDecorator):
    """Aceita strings ISO, datetime nativo e timestamps legados no SQLite."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            normalized = normalized.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                try:
                    return datetime.fromtimestamp(float(normalized), tz=timezone.utc)
                except ValueError:
                    return None
        return None


class User(SQLModel, table=True):
    """Modelo de usuário para autenticação"""

    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    password_plain: Optional[str] = Field(default=None, max_length=200)
    is_admin: bool = Field(default=False)
    setor: Optional[str] = Field(default="geral", max_length=50)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(FlexibleDateTime(), nullable=True),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(FlexibleDateTime(), nullable=True),
    )


class RevokedToken(SQLModel, table=True):
    """Modelo para tokens revogados (persistência de logout)"""

    __tablename__ = "revoked_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime = Field(sa_column=Column(FlexibleDateTime(), nullable=False))
    revoked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(FlexibleDateTime(), nullable=False),
    )


class UserCreate(SQLModel):
    """Schema para criar usuário"""
    username: str
    password: str
    is_admin: bool = False
    setor: str = "geral"


class UserResponse(SQLModel):
    """Schema para resposta de usuário (sem senha)"""
    id: int
    username: str
    is_admin: bool
    is_active: bool
    setor: Optional[str] = None
    password_plain: Optional[str] = None
    created_at: Optional[datetime] = None

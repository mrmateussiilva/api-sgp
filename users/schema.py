from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel


class UserRead(SQLModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    setor: Optional[str] = None
    password_plain: Optional[str] = None
    created_at: Optional[datetime] = None


class UserCreate(SQLModel):
    username: str
    password: str
    is_admin: bool = False
    is_active: bool = True
    setor: str = "geral"


class UserUpdate(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    setor: Optional[str] = None

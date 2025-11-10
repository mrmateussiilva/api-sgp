from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    is_admin: Optional[bool] = None
    session_token: Optional[str] = None
    message: str


class LogoutResponse(BaseModel):
    success: bool
    message: str


class UserResponse(BaseModel):
    user_id: int
    username: str



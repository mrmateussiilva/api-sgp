import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from auth import schema as auth_schema
from auth.models import User
from database.database import get_session

router = APIRouter(tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="ignored")

# Configuração JWT
SECRET_KEY = "your-secret-key-change-in-production-123456789"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha está correta"""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Caso o hash esteja em formato inesperado, compara diretamente (compatibilidade legada)
        return plain_password == hashed_password


def get_password_hash(password: str) -> str:
    """Gera hash da senha"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Cria token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/login")
async def login(
    request: auth_schema.LoginRequest,
    db: AsyncSession = Depends(get_session)
):
    """
    Endpoint de login - Modo Produção
    
    Verifica credenciais no banco de dados
    """
    try:
        # Buscar usuário no banco
        statement = select(User).where(User.username == request.username)
        result = await db.exec(statement)
        user = result.first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário ou senha inválidos"
            )
        
        # Verificar senha
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário ou senha inválidos"
            )

        # Criar token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id},
            expires_delta=access_token_expires
        )
        
        # Verificar is_admin (campo adicionado na tabela)
        is_admin = getattr(user, 'is_admin', False)
        
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "is_admin": bool(is_admin),
            "session_token": access_token,
            "message": "Login realizado com sucesso"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao realizar login: {str(e)}"
        )


@router.post("/logout")
async def logout():
    """
    Endpoint de logout
    """
    return {
        "success": True,
        "message": "Logout realizado com sucesso"
    }


@router.get("/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Retorna informações do usuário atual baseado no token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        return {
            "user_id": user_id,
            "username": username
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

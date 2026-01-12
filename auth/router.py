import bcrypt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from auth import schema as auth_schema
from auth.models import User
from database.database import get_session
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="ignored")

# Configuração JWT
SECRET_KEY = settings.SECRET_KEY.get_secret_value()
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
revoked_tokens: Dict[str, datetime] = {}


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


async def _cleanup_revoked_tokens(session: AsyncSession) -> None:
    """Remove tokens expirados do registro de revogação."""
    now = datetime.now(timezone.utc)
    statement = select(RevokedToken).where(RevokedToken.expires_at <= now)
    result = await session.exec(statement)
    expired_tokens = result.all()
    for token in expired_tokens:
        await session.delete(token)
    await session.commit()


async def _is_token_revoked(token: str, session: AsyncSession) -> bool:
    """Verifica se um token foi revogado (persistido no banco)."""
    statement = select(RevokedToken).where(RevokedToken.token == token)
    result = await session.exec(statement)
    revoked = result.first()
    if revoked and revoked.expires_at > datetime.now(timezone.utc):
        return True
    # Limpar tokens expirados periodicamente
    if revoked and revoked.expires_at <= datetime.now(timezone.utc):
        await session.delete(revoked)
        await session.commit()
    return False


async def _revoke_token(token: str, exp: datetime, session: AsyncSession) -> None:
    """Revoga um token persistindo no banco de dados."""
    # Verificar se já existe
    statement = select(RevokedToken).where(RevokedToken.token == token)
    result = await session.exec(statement)
    existing = result.first()
    
    if existing:
        # Atualizar expiração se necessário
        existing.expires_at = exp
        session.add(existing)
    else:
        # Criar novo registro
        revoked_token = RevokedToken(
            token=token,
            expires_at=exp,
            revoked_at=datetime.now(timezone.utc)
        )
        session.add(revoked_token)
    
    await session.commit()
    await _cleanup_revoked_tokens(session)


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

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo"
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
        logger.exception("Erro ao realizar login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar solicitação de login"
        )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Endpoint de logout
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = payload.get("exp")
        if exp_timestamp is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        _revoke_token(token, exp_datetime)

        return {
            "success": True,
            "message": "Logout realizado com sucesso"
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")


@router.get("/me")
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session)
):
    """
    Retorna informações do usuário atual baseado no token
    """
    try:
        if await _is_token_revoked(token, db):
            raise HTTPException(status_code=401, detail="Token revogado")

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Token inválido")

        user = None
        if user_id:
            user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente")

        return {
            "user_id": user_id,
            "username": username
        }
    except HTTPException:
        raise
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    except Exception as e:
        logger.exception("Erro ao obter usuário atual")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao processar solicitação")
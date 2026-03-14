from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional

from database.database import get_session
from auth.security import decode_access_token
from fastapi.security import OAuth2PasswordBearer

from safira.schemas import SafiraRequest, SafiraResponse
from safira.service import SafiraService

router = APIRouter(tags=["Safira"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

async def get_current_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[int]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    return payload.get("user_id")

@router.post("/ask", response_model=SafiraResponse)
async def ask_safira(
    request: SafiraRequest,
    session: AsyncSession = Depends(get_session),
    user_id: Optional[int] = Depends(get_current_user_id)
):
    service = SafiraService(session)
    try:
        response = await service.ask(request.question, usuario_id=user_id)
        return response
    except Exception as e:
        # Fallback amigável em caso de erro interno
        return SafiraResponse(
            recognized=False,
            intent="error",
            answer="Desculpe, tive um problema técnico ao processar sua pergunta. Pode tentar novamente em alguns instantes?"
        )

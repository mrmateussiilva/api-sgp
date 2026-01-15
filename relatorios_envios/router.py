from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.router import listar_pedidos, MAX_PAGE_SIZE
from pedidos.schema import PedidoResponse, Status


router = APIRouter(prefix="/relatorios-envios", tags=["Relatorios Envios"])


@router.get("/pedidos", response_model=List[PedidoResponse])
async def relatorio_envios(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    status: Optional[Status] = Query(default=None),
    cliente: Optional[str] = Query(default=None),
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
):
    """
    Relatorio de envios (alias dedicado).
    Filtra sempre por data de entrega.
    """
    return await listar_pedidos(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        cliente=cliente,
        data_inicio=data_inicio,
        data_fim=data_fim,
        date_mode="entrega",
    )

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.schema import Pedido, Status
from .schema import RelatorioQuantidadeResponse


router = APIRouter(prefix="/relatorios-fechamentos", tags=["Relatorios Fechamentos"])


def _normalize_date_mode(date_mode: Optional[str]) -> str:
    mode = (date_mode or "entrada").lower().strip()
    if mode not in {"entrada", "entrega"}:
        raise HTTPException(
            status_code=400,
            detail="date_mode invalido. Use: entrada ou entrega",
        )
    return mode


def _apply_date_filters(
    filters,
    date_mode: str,
    data_inicio: Optional[str],
    data_fim: Optional[str],
):
    date_field = Pedido.data_entrada if date_mode == "entrada" else Pedido.data_entrega

    if date_mode == "entrega":
        filters = filters.where(Pedido.data_entrega.isnot(None))

    if data_inicio:
        filters = filters.where(func.date(date_field) >= data_inicio)
    if data_fim:
        filters = filters.where(func.date(date_field) <= data_fim)

    return filters


@router.get("/pedidos/quantidade", response_model=RelatorioQuantidadeResponse)
async def quantidade_pedidos(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[Status] = Query(default=None),
    cliente: Optional[str] = Query(default=None),
) -> RelatorioQuantidadeResponse:
    """Retorna a quantidade de pedidos conforme filtros de fechamento."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        query = select(func.count()).select_from(Pedido)

        if status:
            query = query.where(Pedido.status == status)

        if cliente:
            query = query.where(func.lower(Pedido.cliente).like(f"%{cliente.lower().strip()}%"))

        if data_inicio or data_fim:
            query = _apply_date_filters(query, normalized_mode, data_inicio, data_fim)

        total = (await session.exec(query)).one()
        return RelatorioQuantidadeResponse(
            total=total,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status.value if status else None,
            cliente=cliente,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc

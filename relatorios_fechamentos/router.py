from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.schema import Pedido, Status
from relatorios.fechamentos import (
    calculate_order_value,
    get_fechamento_by_category,
    get_fechamento_trends,
    get_filtered_orders,
)
from .schema import (
    RelatorioQuantidadeResponse,
    RelatorioRankingResponse,
    RelatorioRankingItem,
    RelatorioStatusItem,
    RelatorioStatusResponse,
    RelatorioTrendItem,
    RelatorioTrendResponse,
    RelatorioValorTotalResponse,
)


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


@router.get("/pedidos/por-status", response_model=RelatorioStatusResponse)
async def quantidade_por_status(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    cliente: Optional[str] = Query(default=None),
) -> RelatorioStatusResponse:
    """Retorna quantidade de pedidos agrupada por status."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        query = select(Pedido.status, func.count()).group_by(Pedido.status).order_by(func.count().desc())

        if cliente:
            query = query.where(func.lower(Pedido.cliente).like(f"%{cliente.lower().strip()}%"))

        if data_inicio or data_fim:
            query = _apply_date_filters(query, normalized_mode, data_inicio, data_fim)

        rows = (await session.exec(query)).all()
        items = [
            RelatorioStatusItem(status=row[0].value if hasattr(row[0], "value") else str(row[0]), total=row[1])
            for row in rows
        ]
        return RelatorioStatusResponse(
            items=items,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            cliente=cliente,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/por-cliente", response_model=RelatorioRankingResponse)
async def ranking_por_cliente(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de resultados"),
) -> RelatorioRankingResponse:
    """Ranking de pedidos por cliente."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        ranking_raw = await get_fechamento_by_category(
            session,
            category="cliente",
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            limit=limit,
        )
        ranking = [RelatorioRankingItem(**item) for item in ranking_raw]
        return RelatorioRankingResponse(
            category="cliente",
            items=ranking,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/por-vendedor", response_model=RelatorioRankingResponse)
async def ranking_por_vendedor(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de resultados"),
) -> RelatorioRankingResponse:
    """Ranking de pedidos por vendedor."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        ranking_raw = await get_fechamento_by_category(
            session,
            category="vendedor",
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            limit=limit,
        )
        ranking = [RelatorioRankingItem(**item) for item in ranking_raw]
        return RelatorioRankingResponse(
            category="vendedor",
            items=ranking,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/por-designer", response_model=RelatorioRankingResponse)
async def ranking_por_designer(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de resultados"),
) -> RelatorioRankingResponse:
    """Ranking de pedidos por designer."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        ranking_raw = await get_fechamento_by_category(
            session,
            category="designer",
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            limit=limit,
        )
        ranking = [RelatorioRankingItem(**item) for item in ranking_raw]
        return RelatorioRankingResponse(
            category="designer",
            items=ranking,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/por-tipo-producao", response_model=RelatorioRankingResponse)
async def ranking_por_tipo_producao(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de resultados"),
) -> RelatorioRankingResponse:
    """Ranking de pedidos por tipo de producao."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        ranking_raw = await get_fechamento_by_category(
            session,
            category="tipo_producao",
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            limit=limit,
        )
        ranking = [RelatorioRankingItem(**item) for item in ranking_raw]
        return RelatorioRankingResponse(
            category="tipo_producao",
            items=ranking,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/tendencia", response_model=RelatorioTrendResponse)
async def tendencia_pedidos(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    group_by: str = Query("day", description="Agrupamento: 'day', 'week' ou 'month'"),
) -> RelatorioTrendResponse:
    """Tendencia de pedidos por periodo."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        trends_raw = await get_fechamento_trends(
            session,
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            group_by=group_by,
        )
        trends = [RelatorioTrendItem(**item) for item in trends_raw]
        return RelatorioTrendResponse(
            group_by=group_by,
            items=trends,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc


@router.get("/pedidos/valor-total", response_model=RelatorioValorTotalResponse)
async def valor_total_pedidos(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    cliente: Optional[str] = Query(None, description="Nome do cliente"),
    vendedor: Optional[str] = Query(None, description="Nome do vendedor"),
    designer: Optional[str] = Query(None, description="Nome do designer"),
) -> RelatorioValorTotalResponse:
    """Totaliza valor dos pedidos conforme filtros."""
    try:
        normalized_mode = _normalize_date_mode(date_mode)
        pedidos_with_items = await get_filtered_orders(
            session,
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=normalized_mode,
            vendedor=vendedor,
            designer=designer,
            cliente=cliente,
        )
        total = 0.0
        for pedido, items in pedidos_with_items:
            total += calculate_order_value(pedido, items)
        total = round(total, 2)
        return RelatorioValorTotalResponse(
            total_pedidos=len(pedidos_with_items),
            valor_total=total,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=normalized_mode,
            status=status,
            cliente=cliente,
            vendedor=vendedor,
            designer=designer,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao gerar relatorio: {exc}"
        ) from exc

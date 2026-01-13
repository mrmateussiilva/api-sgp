from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.schema import Pedido, PedidoResponse, Status
from relatorios.fechamentos import (
    calculate_order_value,
    get_fechamento_by_category,
    get_fechamento_trends,
    get_filtered_orders,
    get_item_value,
    json_string_to_items,
    parse_currency,
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

REPORT_TYPES = {
    "analitico_designer_cliente",
    "analitico_cliente_designer",
    "analitico_cliente_painel",
    "analitico_designer_painel",
    "analitico_entrega_painel",
    "analitico_vendedor_designer",
    "analitico_designer_vendedor",
    "sintetico_data",
    "sintetico_data_entrada",
    "sintetico_data_entrega",
    "sintetico_designer",
    "sintetico_vendedor",
    "sintetico_vendedor_designer",
    "sintetico_cliente",
    "sintetico_entrega",
}

REPORT_TITLES = {
    "analitico_designer_cliente": "Relatório Analítico — Designer × Cliente",
    "analitico_cliente_designer": "Relatório Analítico — Cliente × Designer",
    "analitico_cliente_painel": "Relatório Analítico — Cliente × Tipo de Produção",
    "analitico_designer_painel": "Relatório Analítico — Designer × Tipo de Produção",
    "analitico_entrega_painel": "Relatório Analítico — Forma de Entrega × Tipo de Produção",
    "analitico_vendedor_designer": "Relatório Analítico — Vendedor × Designer",
    "analitico_designer_vendedor": "Relatório Analítico — Designer × Vendedor",
    "sintetico_data": "Relatório Sintético — Totais por Data (referência automática)",
    "sintetico_data_entrada": "Relatório Sintético — Totais por Data de Entrada",
    "sintetico_data_entrega": "Relatório Sintético — Totais por Data de Entrega",
    "sintetico_designer": "Relatório Sintético — Totais por Designer",
    "sintetico_vendedor": "Relatório Sintético — Totais por Vendedor",
    "sintetico_vendedor_designer": "Relatório Sintético — Totais por Vendedor/Designer",
    "sintetico_cliente": "Relatório Sintético — Totais por Cliente",
    "sintetico_entrega": "Relatório Sintético — Totais por Forma de Entrega",
}


def _normalize_text(value: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _slugify(value: str) -> str:
    cleaned = _normalize_text(value)
    slug = []
    prev_hyphen = False
    for ch in cleaned:
        if ch.isalnum():
            slug.append(ch)
            prev_hyphen = False
        else:
            if not prev_hyphen:
                slug.append("-")
                prev_hyphen = True
    return "".join(slug).strip("-")


def _parse_query_date(value: Optional[str], label: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{label} invalida. Use YYYY-MM-DD") from exc


def _parse_order_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _date_in_range(value: Optional[date], start: Optional[date], end: Optional[date]) -> bool:
    if value is None:
        return False
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def _matches_status(pedido: Pedido, status: Optional[str]) -> bool:
    if not status or _normalize_text(status) == "todos":
        return True
    normalized = _normalize_text(status)
    status_map = {
        "pendente": {Status.PENDENTE},
        "em processamento": {Status.EM_PRODUCAO},
        "em producao": {Status.EM_PRODUCAO},
        "em_producao": {Status.EM_PRODUCAO},
        "concluido": {Status.PRONTO, Status.ENTREGUE},
        "cancelado": {Status.CANCELADO},
    }
    if normalized not in status_map:
        raise HTTPException(status_code=400, detail="status invalido")
    return pedido.status in status_map[normalized]


def _format_period_label(start: Optional[date], end: Optional[date]) -> str:
    if start and end:
        return f"Período: {start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
    if start:
        return f"Período: {start.strftime('%d/%m/%Y')}"
    if end:
        return f"Período: {end.strftime('%d/%m/%Y')}"
    return "Período não especificado"


def _format_status_label(status: Optional[str]) -> str:
    if not status or _normalize_text(status) == "todos":
        return "Status: Todos"
    normalized = _normalize_text(status)
    display_map = {
        "pendente": "Pendente",
        "em processamento": "Em Processamento",
        "em producao": "Em Processamento",
        "em_producao": "Em Processamento",
        "concluido": "Concluído",
        "cancelado": "Cancelado",
    }
    if normalized not in display_map:
        raise HTTPException(status_code=400, detail="status invalido")
    return f"Status: {display_map[normalized]}"


def _get_effective_date(pedido: Pedido) -> Optional[date]:
    return _parse_order_date(pedido.data_entrega) or _parse_order_date(pedido.data_entrada)


def _filter_by_date(
    pedido: Pedido,
    start: Optional[date],
    end: Optional[date],
    date_mode: Optional[str],
) -> bool:
    if not start and not end:
        return True
    if not date_mode:
        return _date_in_range(_get_effective_date(pedido), start, end)
    normalized = date_mode.lower().strip()
    if normalized == "entrada":
        return _date_in_range(_parse_order_date(pedido.data_entrada), start, end)
    if normalized == "entrega":
        return _date_in_range(_parse_order_date(pedido.data_entrega), start, end)
    # if normalized == "qualquer":
    #     return _date_in_range(_parse_order_date(pedido.data_entrada), start, end) or _date_in_range(
    #         _parse_order_date(pedido.data_entrega),
    #         start,
    #         end,
    #     )
    raise HTTPException(status_code=400, detail="date_mode invalido")


def _normalize_name(value: Optional[str], default: str) -> str:
    cleaned = (value or "").strip()
    return cleaned if cleaned else default


def _group_sort_key(value: str) -> str:
    return _normalize_text(value)


def _normalize_frete_distribution(value: Optional[str], report_type: str) -> str:
    if not value:
        return "por_pedido"
    normalized = value.lower().strip()
    if normalized not in {"por_pedido", "proporcional"}:
        raise HTTPException(status_code=400, detail="frete_distribution invalido")
    return normalized


def _build_row(item: Any, pedido: Pedido, valor_frete: float, valor_servico: float) -> Dict[str, Any]:
    ficha = pedido.numero or str(pedido.id or "")
    descricao = getattr(item, "descricao", None) or getattr(item, "tipo_producao", None) or "Item"
    return {
        "ficha": ficha,
        "descricao": descricao,
        "valor_frete": round(valor_frete, 2),
        "valor_servico": round(valor_servico, 2),
    }


def _format_group_label(prefix: str, value: Optional[str], default: str) -> Tuple[str, str]:
    label_value = _normalize_name(value, default)
    label = f"{prefix}: {label_value}"
    return _slugify(label), label


def _format_date_group(prefix: str, value: Optional[date]) -> Tuple[str, str]:
    if value:
        label = f"{prefix}: {value.strftime('%d/%m/%Y')}"
    else:
        label = f"{prefix}: Sem data"
    return _slugify(label), label


def _get_analitico_keys(report_type: str, pedido: Pedido, item: Any) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    if report_type == "analitico_designer_cliente":
        group = _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
        subgroup = _format_group_label("Cliente", pedido.cliente, "Cliente não informado")
        return group, subgroup
    if report_type == "analitico_cliente_designer":
        group = _format_group_label("Cliente", pedido.cliente, "Cliente não informado")
        subgroup = _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
        return group, subgroup
    if report_type == "analitico_cliente_painel":
        group = _format_group_label("Cliente", pedido.cliente, "Cliente não informado")
        subgroup = _format_group_label("Tipo de Produção", getattr(item, "tipo_producao", None), "Sem tipo")
        return group, subgroup
    if report_type == "analitico_designer_painel":
        group = _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
        subgroup = _format_group_label("Tipo de Produção", getattr(item, "tipo_producao", None), "Sem tipo")
        return group, subgroup
    if report_type == "analitico_entrega_painel":
        group = _format_group_label("Forma de Entrega", pedido.forma_envio, "Sem forma de envio")
        subgroup = _format_group_label("Tipo de Produção", getattr(item, "tipo_producao", None), "Sem tipo")
        return group, subgroup
    if report_type == "analitico_vendedor_designer":
        group = _format_group_label("Vendedor", getattr(item, "vendedor", None), "Sem vendedor")
        subgroup = _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
        return group, subgroup
    if report_type == "analitico_designer_vendedor":
        group = _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
        subgroup = _format_group_label("Vendedor", getattr(item, "vendedor", None), "Sem vendedor")
        return group, subgroup
    raise HTTPException(status_code=400, detail="report_type invalido")


def _get_sintetico_group(
    report_type: str,
    pedido: Pedido,
    item: Any,
    date_mode: Optional[str],
) -> Tuple[str, str]:
    if report_type == "sintetico_data":
        if date_mode == "entrada":
            return _format_date_group("Data", _parse_order_date(pedido.data_entrada))
        if date_mode == "entrega":
            return _format_date_group("Data", _parse_order_date(pedido.data_entrega))
        return _format_date_group("Data", _get_effective_date(pedido))
    if report_type == "sintetico_data_entrada":
        return _format_date_group("Data Entrada", _parse_order_date(pedido.data_entrada))
    if report_type == "sintetico_data_entrega":
        return _format_date_group("Data Entrega", _parse_order_date(pedido.data_entrega))
    if report_type == "sintetico_designer":
        return _format_group_label("Designer", getattr(item, "designer", None), "Sem designer")
    if report_type == "sintetico_vendedor":
        return _format_group_label("Vendedor", getattr(item, "vendedor", None), "Sem vendedor")
    if report_type == "sintetico_vendedor_designer":
        vendedor = _normalize_name(getattr(item, "vendedor", None), "Sem vendedor")
        designer = _normalize_name(getattr(item, "designer", None), "Sem designer")
        label = f"Vendedor/Designer: {vendedor} / {designer}"
        return _slugify(label), label
    if report_type == "sintetico_cliente":
        return _format_group_label("Cliente", pedido.cliente, "Cliente não informado")
    if report_type == "sintetico_entrega":
        return _format_group_label("Forma de Entrega", pedido.forma_envio, "Sem forma de envio")
    raise HTTPException(status_code=400, detail="report_type invalido")


def _ensure_group(groups: Dict[str, Dict[str, Any]], key: str, label: str, use_subgroups: bool) -> Dict[str, Any]:
    if key not in groups:
        groups[key] = {
            "key": key,
            "label": label,
            "rows": [],
            "subgroups": {} if use_subgroups else None,
            "subtotal": {"valor_frete": 0.0, "valor_servico": 0.0, "_desconto": 0.0},
            "_pedido_ids": set(),
            "_desconto_ids": set(),
            "_items_count": 0,
        }
    return groups[key]


def _ensure_subgroup(group: Dict[str, Any], key: str, label: str) -> Dict[str, Any]:
    subgroups = group["subgroups"]
    if key not in subgroups:
        subgroups[key] = {
            "key": key,
            "label": label,
            "rows": [],
            "subtotal": {"valor_frete": 0.0, "valor_servico": 0.0, "_desconto": 0.0},
            "_pedido_ids": set(),
            "_desconto_ids": set(),
        }
    return subgroups[key]


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


@router.get("/pedidos/relatorio")
async def relatorio_fechamentos(
    session: AsyncSession = Depends(get_session),
    report_type: str = Query(..., description="Tipo de relatorio"),
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Status do pedido"),
    date_mode: Optional[str] = Query(None, description="Modo de data: entrada, entrega ou qualquer"),
    vendedor: Optional[str] = Query(None, description="Filtro parcial por vendedor"),
    designer: Optional[str] = Query(None, description="Filtro parcial por designer"),
    cliente: Optional[str] = Query(None, description="Filtro parcial por cliente"),
    frete_distribution: Optional[str] = Query(None, description="por_pedido ou proporcional"),
) -> Dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail="report_type invalido")

    start = _parse_query_date(start_date, "start_date")
    end = _parse_query_date(end_date, "end_date")
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start_date deve ser menor ou igual a end_date")

    normalized_date_mode = date_mode.lower().strip() if date_mode else None
    if normalized_date_mode and normalized_date_mode not in {"entrada", "entrega", "qualquer"}:
        raise HTTPException(status_code=400, detail="date_mode invalido")

    frete_mode = _normalize_frete_distribution(frete_distribution, report_type)

    filtro_vendedor = _normalize_text(vendedor) if vendedor else None
    filtro_designer = _normalize_text(designer) if designer else None
    filtro_cliente = _normalize_text(cliente) if cliente else None

    query = select(Pedido)
    start_value = start.strftime("%Y-%m-%d")
    end_value = end.strftime("%Y-%m-%d")

    if normalized_date_mode == "entrada":
        query = query.where(
            func.date(Pedido.data_entrada) >= start_value,
            func.date(Pedido.data_entrada) <= end_value,
        )
    elif normalized_date_mode == "entrega":
        query = query.where(
            Pedido.data_entrega.isnot(None),
            func.date(Pedido.data_entrega) >= start_value,
            func.date(Pedido.data_entrega) <= end_value,
        )
    else:
        query = query.where(
            or_(
                and_(
                    func.date(Pedido.data_entrada) >= start_value,
                    func.date(Pedido.data_entrada) <= end_value,
                ),
                and_(
                    func.date(Pedido.data_entrega) >= start_value,
                    func.date(Pedido.data_entrega) <= end_value,
                ),
            )
        )

    result = await session.exec(query)
    pedidos = result.all()

    groups: Dict[str, Dict[str, Any]] = {}
    total = {"valor_frete": 0.0, "valor_servico": 0.0, "_desconto": 0.0}
    total_frete_ids: set[int] = set()
    total_desconto_ids: set[int] = set()

    for pedido in pedidos:
        pedido_id = int(pedido.id or 0)
        if not _matches_status(pedido, status):
            continue
        if filtro_cliente:
            if not pedido.cliente or filtro_cliente not in _normalize_text(pedido.cliente):
                continue
        if not _filter_by_date(pedido, start, end, normalized_date_mode):
            continue

        items = json_string_to_items(pedido.items or "[]")
        if filtro_vendedor or filtro_designer:
            filtered_items = []
            for item in items:
                if filtro_vendedor:
                    item_vendedor = _normalize_text(getattr(item, "vendedor", "") or "")
                    if filtro_vendedor not in item_vendedor:
                        continue
                if filtro_designer:
                    item_designer = _normalize_text(getattr(item, "designer", "") or "")
                    if filtro_designer not in item_designer:
                        continue
                filtered_items.append(item)
            items = filtered_items

        if not items:
            continue

        item_values = [get_item_value(item) for item in items]
        total_servico_pedido = sum(item_values)
        frete_total = parse_currency(pedido.valor_frete) or 0.0
        pedido_valor_total = parse_currency(pedido.valor_total) or 0.0
        desconto = 0.0
        if pedido_valor_total:
            desconto = max(0.0, (total_servico_pedido + frete_total) - pedido_valor_total)

        if frete_mode == "proporcional" and total_servico_pedido > 0:
            frete_items = [frete_total * (value / total_servico_pedido) for value in item_values]
        elif frete_mode == "proporcional":
            frete_items = [0.0 for _ in item_values]
        else:
            frete_items = [frete_total for _ in item_values]

        total["valor_servico"] += total_servico_pedido
        if frete_mode == "proporcional":
            total["valor_frete"] += sum(frete_items)
        else:
            if pedido_id not in total_frete_ids:
                total["valor_frete"] += frete_total
                total_frete_ids.add(pedido_id)
        if desconto > 0 and pedido_id not in total_desconto_ids:
            total["_desconto"] += desconto
            total_desconto_ids.add(pedido_id)

        is_analitico = report_type.startswith("analitico_")

        for item, item_value, item_frete in zip(items, item_values, frete_items):
            if is_analitico:
                group_info, subgroup_info = _get_analitico_keys(report_type, pedido, item)
                group_key, group_label = group_info
                subgroup_key, subgroup_label = subgroup_info
                group = _ensure_group(groups, group_key, group_label, use_subgroups=True)
                subgroup = _ensure_subgroup(group, subgroup_key, subgroup_label)
                subgroup["rows"].append(_build_row(item, pedido, item_frete, item_value))
                subgroup["subtotal"]["valor_servico"] += item_value
                if frete_mode == "proporcional":
                    subgroup["subtotal"]["valor_frete"] += item_frete
                else:
                    if pedido_id not in subgroup["_pedido_ids"]:
                        subgroup["subtotal"]["valor_frete"] += frete_total
                        subgroup["_pedido_ids"].add(pedido_id)
                if desconto > 0 and pedido_id not in subgroup["_desconto_ids"]:
                    subgroup["subtotal"]["_desconto"] += desconto
                    subgroup["_desconto_ids"].add(pedido_id)

                group["subtotal"]["valor_servico"] += item_value
                if frete_mode == "proporcional":
                    group["subtotal"]["valor_frete"] += item_frete
                else:
                    if pedido_id not in group["_pedido_ids"]:
                        group["subtotal"]["valor_frete"] += frete_total
                        group["_pedido_ids"].add(pedido_id)
                if desconto > 0 and pedido_id not in group["_desconto_ids"]:
                    group["subtotal"]["_desconto"] += desconto
                    group["_desconto_ids"].add(pedido_id)
            else:
                group_key, group_label = _get_sintetico_group(
                    report_type,
                    pedido,
                    item,
                    normalized_date_mode,
                )
                group = _ensure_group(groups, group_key, group_label, use_subgroups=False)
                group["_items_count"] += 1
                group["subtotal"]["valor_servico"] += item_value
                if frete_mode == "proporcional":
                    group["subtotal"]["valor_frete"] += item_frete
                else:
                    if pedido_id not in group["_pedido_ids"]:
                        group["subtotal"]["valor_frete"] += frete_total
                group["_pedido_ids"].add(pedido_id)
                if desconto > 0 and pedido_id not in group["_desconto_ids"]:
                    group["subtotal"]["_desconto"] += desconto
                    group["_desconto_ids"].add(pedido_id)

    def _finalize_subtotal(data: Dict[str, Any]) -> Dict[str, Any]:
        frete = round(data.get("valor_frete", 0.0), 2)
        servico = round(data.get("valor_servico", 0.0), 2)
        subtotal = {"valor_frete": frete, "valor_servico": servico}
        desconto_value = round(data.get("_desconto", 0.0), 2)
        if desconto_value > 0:
            subtotal["desconto"] = desconto_value
            subtotal["valor_liquido"] = round(frete + servico - desconto_value, 2)
        return subtotal

    group_list: List[Dict[str, Any]] = list(groups.values())
    group_list.sort(key=lambda item: _group_sort_key(item["label"]))

    for group in group_list:
        if group.get("subgroups") is not None:
            subgroup_list = list(group["subgroups"].values())
            subgroup_list.sort(key=lambda item: _group_sort_key(item["label"]))
            for subgroup in subgroup_list:
                subgroup["subtotal"] = _finalize_subtotal(subgroup["subtotal"])
                subgroup.pop("_pedido_ids", None)
                subgroup.pop("_desconto_ids", None)
            group["subgroups"] = subgroup_list
        else:
            pedidos_count = len(group.get("_pedido_ids", []))
            items_count = group.get("_items_count", 0)
            group["rows"] = [
                {
                    "ficha": f"Pedidos: {pedidos_count} · Itens: {items_count}",
                    "descricao": "Subtotal",
                    "valor_frete": round(group["subtotal"]["valor_frete"], 2),
                    "valor_servico": round(group["subtotal"]["valor_servico"], 2),
                }
            ]
            group.pop("subgroups", None)

        group["subtotal"] = _finalize_subtotal(group["subtotal"])
        group.pop("_pedido_ids", None)
        group.pop("_desconto_ids", None)
        group.pop("_items_count", None)

    total_final = _finalize_subtotal(total)

    response = {
        "title": REPORT_TITLES[report_type],
        "period_label": _format_period_label(start, end),
        "status_label": _format_status_label(status),
        "page": 1,
        "generated_at": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
        "report_type": report_type,
        "groups": group_list,
        "total": total_final,
    }
    return response


@router.get("/pedidos/relatorio-semanal", response_model=List[PedidoResponse])
async def relatorio_semanal(
    session: AsyncSession = Depends(get_session),
    start_date: str = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Data final (YYYY-MM-DD)"),
    date_mode: Optional[str] = Query("entrada", description="Modo de data: entrada, entrega ou qualquer"),
) -> List[PedidoResponse]:
    """Retorna todos os pedidos do intervalo informado."""
    start = _parse_query_date(start_date, "start_date")
    end = _parse_query_date(end_date, "end_date")
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start_date deve ser menor ou igual a end_date")

    normalized_date_mode = date_mode.lower().strip() if date_mode else None
    if normalized_date_mode and normalized_date_mode not in {"entrada", "entrega", "qualquer"}:
        raise HTTPException(status_code=400, detail="date_mode invalido")

    query = select(Pedido)
    start_value = start.strftime("%Y-%m-%d")
    end_value = end.strftime("%Y-%m-%d")

    if normalized_date_mode == "entrada":
        query = query.where(
            func.date(Pedido.data_entrada) >= start_value,
            func.date(Pedido.data_entrada) <= end_value,
        )
    elif normalized_date_mode == "entrega":
        query = query.where(
            Pedido.data_entrega.isnot(None),
            func.date(Pedido.data_entrega) >= start_value,
            func.date(Pedido.data_entrega) <= end_value,
        )
    else:
        query = query.where(
            or_(
                and_(
                    func.date(Pedido.data_entrada) >= start_value,
                    func.date(Pedido.data_entrada) <= end_value,
                ),
                and_(
                    func.date(Pedido.data_entrega) >= start_value,
                    func.date(Pedido.data_entrega) <= end_value,
                ),
            )
        )

    result = await session.exec(query)
    pedidos = result.all()
    response: List[PedidoResponse] = []
    for pedido in pedidos:
        items = json_string_to_items(pedido.items or "[]")
        pedido_payload = pedido.model_dump()
        pedido_payload.pop("items", None)
        pedido_payload.pop("data_criacao", None)
        pedido_payload.pop("ultima_atualizacao", None)
        response.append(
            PedidoResponse(
                **pedido_payload,
                items=items,
                data_criacao=pedido.data_criacao,
                ultima_atualizacao=pedido.ultima_atualizacao,
            )
        )
    return response

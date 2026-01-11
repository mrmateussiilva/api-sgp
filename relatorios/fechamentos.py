"""
Módulo para cálculos de estatísticas de fechamentos.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
from sqlmodel import select, func, and_, or_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text

from pedidos.schema import Pedido, ItemPedido, Status


def parse_currency(value: Any) -> float:
    """Converte valor para float, tratando strings e números."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        # Remove formatação de moeda
        cleaned = value.replace("R$", "").replace("$", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def calculate_order_value(pedido: Pedido, items: List[ItemPedido]) -> float:
    """Calcula o valor total de um pedido."""
    # Tenta usar total_value primeiro
    if pedido.total_value:
        return parse_currency(pedido.total_value)
    
    # Calcula a partir dos itens
    items_sum = sum(
        parse_currency(item.subtotal) or (parse_currency(item.quantity) * parse_currency(item.unit_price))
        for item in items
    )
    
    frete = parse_currency(pedido.valor_frete) or 0.0
    return items_sum + frete


async def get_filtered_orders(
    session: AsyncSession,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    date_mode: str = "entrega",  # "entrada" ou "entrega"
    vendedor: Optional[str] = None,
    designer: Optional[str] = None,
    cliente: Optional[str] = None,
) -> List[tuple[Pedido, List[ItemPedido]]]:
    """Busca pedidos com filtros aplicados."""
    # Query base
    query = select(Pedido)
    conditions = []
    
    # Filtro por data
    if start_date or end_date:
        date_field = "data_entrega" if date_mode == "entrega" else "data_entrada"
        date_attr = getattr(Pedido, date_field)
        
        # Quando há filtro de data, só considerar pedidos com data preenchida
        if date_mode == "entrega":
            conditions.append(Pedido.data_entrega.isnot(None))
        
        if start_date:
            conditions.append(date_attr >= start_date)
        if end_date:
            # Para incluir todo o dia, usar < (end_date + 1 dia)
            try:
                fim_date = datetime.strptime(end_date, "%Y-%m-%d")
                fim_plus_one = (fim_date + timedelta(days=1)).strftime("%Y-%m-%d")
                conditions.append(date_attr < fim_plus_one)
            except (ValueError, TypeError):
                # Fallback: usar <= end_date + "T23:59:59" para incluir todo o dia
                conditions.append(date_attr <= end_date + "T23:59:59")
    
    # Filtro por status
    if status and status.lower() != "todos":
        status_map = {
            "pendente": Status.PENDENTE,
            "em processamento": Status.EM_PRODUCAO,
            "em_producao": Status.EM_PRODUCAO,
            "concluido": Status.PRONTO,
            "pronto": Status.PRONTO,
            "cancelado": Status.CANCELADO,
        }
        normalized_status = status.lower().strip()
        if normalized_status in status_map:
            conditions.append(Pedido.status == status_map[normalized_status])
    
    # Filtro por cliente
    if cliente:
        conditions.append(Pedido.cliente.ilike(f"%{cliente}%"))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await session.exec(query)
    pedidos = result.all()
    
    # Buscar itens para cada pedido
    pedidos_with_items = []
    for pedido in pedidos:
        items_query = select(ItemPedido).where(ItemPedido.order_id == pedido.id)
        items_result = await session.exec(items_query)
        items = items_result.all()
        
        # Aplicar filtros de vendedor/designer nos itens
        if vendedor or designer:
            filtered_items = []
            for item in items:
                if vendedor and item.vendedor and vendedor.lower() not in item.vendedor.lower():
                    continue
                if designer and item.designer and designer.lower() not in item.designer.lower():
                    continue
                filtered_items.append(item)
            items = filtered_items
        
        if items or not (vendedor or designer):  # Inclui pedidos sem itens se não há filtro de vendedor/designer
            pedidos_with_items.append((pedido, items))
    
    return pedidos_with_items


async def get_fechamento_statistics(
    session: AsyncSession,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    date_mode: str = "entrega",
    vendedor: Optional[str] = None,
    designer: Optional[str] = None,
    cliente: Optional[str] = None,
) -> Dict[str, Any]:
    """Calcula estatísticas de fechamentos."""
    pedidos_with_items = await get_filtered_orders(
        session, start_date, end_date, status, date_mode, vendedor, designer, cliente
    )
    
    total_pedidos = len(pedidos_with_items)
    total_items = sum(len(items) for _, items in pedidos_with_items)
    
    total_revenue = 0.0
    total_frete = 0.0
    total_servico = 0.0
    
    for pedido, items in pedidos_with_items:
        order_value = calculate_order_value(pedido, items)
        total_revenue += order_value
        
        frete = parse_currency(pedido.valor_frete) or 0.0
        total_frete += frete
        
        items_value = sum(
            parse_currency(item.subtotal) or (parse_currency(item.quantity) * parse_currency(item.unit_price))
            for item in items
        )
        total_servico += items_value
    
    average_ticket = total_revenue / total_pedidos if total_pedidos > 0 else 0.0
    
    return {
        "total_pedidos": total_pedidos,
        "total_items": total_items,
        "total_revenue": round(total_revenue, 2),
        "total_frete": round(total_frete, 2),
        "total_servico": round(total_servico, 2),
        "average_ticket": round(average_ticket, 2),
    }


async def get_fechamento_trends(
    session: AsyncSession,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    date_mode: str = "entrega",
    group_by: str = "day",  # "day", "week", "month"
) -> List[Dict[str, Any]]:
    """Retorna tendências de fechamentos agrupadas por período."""
    pedidos_with_items = await get_filtered_orders(
        session, start_date, end_date, status, date_mode
    )
    
    # Agrupar por período
    trends_map: Dict[str, Dict[str, float]] = {}
    
    for pedido, items in pedidos_with_items:
        date_field = pedido.data_entrega if date_mode == "entrega" else pedido.data_entrada
        if not date_field:
            continue
        
        # Determinar chave de agrupamento
        if group_by == "day":
            period_key = date_field[:10]  # YYYY-MM-DD
        elif group_by == "week":
            # Calcular semana (simplificado)
            d = datetime.fromisoformat(date_field[:10])
            week_start = d - timedelta(days=d.weekday())
            period_key = week_start.strftime("%Y-W%U")
        else:  # month
            period_key = date_field[:7]  # YYYY-MM
        
        if period_key not in trends_map:
            trends_map[period_key] = {
                "period": period_key,
                "pedidos": 0,
                "revenue": 0.0,
                "frete": 0.0,
                "servico": 0.0,
            }
        
        trends_map[period_key]["pedidos"] += 1
        order_value = calculate_order_value(pedido, items)
        trends_map[period_key]["revenue"] += order_value
        
        frete = parse_currency(pedido.valor_frete) or 0.0
        trends_map[period_key]["frete"] += frete
        
        items_value = sum(
            parse_currency(item.subtotal) or (parse_currency(item.quantity) * parse_currency(item.unit_price))
            for item in items
        )
        trends_map[period_key]["servico"] += items_value
    
    # Converter para lista e ordenar
    trends = list(trends_map.values())
    for trend in trends:
        trend["revenue"] = round(trend["revenue"], 2)
        trend["frete"] = round(trend["frete"], 2)
        trend["servico"] = round(trend["servico"], 2)
    
    trends.sort(key=lambda x: x["period"])
    return trends


async def get_fechamento_by_category(
    session: AsyncSession,
    category: str,  # "vendedor", "designer", "cliente", "tipo_producao"
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    date_mode: str = "entrega",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Retorna ranking por categoria."""
    pedidos_with_items = await get_filtered_orders(
        session, start_date, end_date, status, date_mode
    )
    
    category_map: Dict[str, Dict[str, Any]] = {}
    
    for pedido, items in pedidos_with_items:
        for item in items:
            if category == "vendedor":
                key = item.vendedor or "Sem vendedor"
            elif category == "designer":
                key = item.designer or "Sem designer"
            elif category == "cliente":
                key = pedido.cliente or "Sem cliente"
            elif category == "tipo_producao":
                key = item.tipo_producao or "Sem tipo"
            else:
                continue
            
            if key not in category_map:
                category_map[key] = {
                    "name": key,
                    "pedidos": set(),
                    "items": 0,
                    "revenue": 0.0,
                }
            
            category_map[key]["pedidos"].add(pedido.id)
            category_map[key]["items"] += item.quantity or 1
            
            item_value = parse_currency(item.subtotal) or (
                parse_currency(item.quantity) * parse_currency(item.unit_price)
            )
            category_map[key]["revenue"] += item_value
    
    # Converter para lista e processar
    result = []
    for key, data in category_map.items():
        result.append({
            "name": data["name"],
            "pedidos": len(data["pedidos"]),
            "items": data["items"],
            "revenue": round(data["revenue"], 2),
        })
    
    # Ordenar por receita e limitar
    result.sort(key=lambda x: x["revenue"], reverse=True)
    return result[:limit]

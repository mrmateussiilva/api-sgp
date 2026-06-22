from typing import Optional, List, Dict, Set, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from relatorios.fechamentos import (
    get_filtered_orders,
    calculate_order_value,
    get_item_value,
    parse_currency,
)
from materiais.stock_service import calculate_item_consumption_meters
from .schema import (
    PedidoMetragemItem,
    PedidoMetragemResponse,
    ProducaoTipoEstatisticaItem,
    ProducaoTipoEstatisticaResponse,
    ProducaoTecidoEstatisticaItem,
    ProducaoTecidoEstatisticaResponse,
    AlertaPedidoItem,
    AlertasProducaoResponse,
)

router = APIRouter(prefix="/automacao", tags=["Automação"])


def get_item_quantity(item: Any) -> float:
    """Retorna a quantidade do item com base nos campos dinâmicos da produção."""
    tipo = (getattr(item, 'tipo_producao', None) or "").strip().lower()
    tipo_map = {
        "painel": getattr(item, 'quantidade_paineis', None),
        "generica": getattr(item, 'quantidade_paineis', None),
        "totem": getattr(item, 'quantidade_totem', None),
        "lona": getattr(item, 'quantidade_lona', None),
        "adesivo": getattr(item, 'quantidade_adesivo', None),
    }
    quantity_value = 1.0
    
    # Se o tipo de produção tiver um campo específico mapeado, usar ele
    if tipo in tipo_map and tipo_map[tipo] is not None:
        return parse_currency(tipo_map[tipo])
    
    # Caso contrário, procurar nos campos gerais de quantidade
    quantity_candidates = [
        getattr(item, 'quantity', None),
        getattr(item, 'quantidade', None),
        getattr(item, 'quantidade_paineis', None),
        getattr(item, 'quantidade_totem', None),
        getattr(item, 'quantidade_lona', None),
        getattr(item, 'quantidade_adesivo', None),
    ]
    for raw_value in quantity_candidates:
        value = parse_currency(raw_value)
        if value > quantity_value:
            quantity_value = value
            
    return quantity_value


@router.get("/pedidos/metragem", response_model=PedidoMetragemResponse)
async def list_pedidos_metragem(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
    cliente: Optional[str] = Query(None, description="Nome do cliente"),
):
    """
    Lista pedidos com a metragem quadrada total calculada por pedido.
    Útil para auditoria e acompanhamento de produção em m².
    """
    try:
        mode = date_mode.lower().strip()
        if mode not in ("entrada", "entrega"):
            raise HTTPException(status_code=400, detail="date_mode inválido. Use 'entrada' ou 'entrega'.")

        pedidos_with_items = await get_filtered_orders(
            session=session,
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=mode,
            cliente=cliente,
        )

        items_list = []
        for pedido, items in pedidos_with_items:
            # Calcular metragem total do pedido multiplicando a metragem unitária de cada item pela sua quantidade
            total_metragem = sum(
                calculate_item_consumption_meters(item) * get_item_quantity(item) 
                for item in items
            )
            
            # Valor total do pedido
            valor_total = calculate_order_value(pedido, items)
            
            # Status como string
            status_str = pedido.status.value if hasattr(pedido.status, "value") else str(pedido.status)

            items_list.append(
                PedidoMetragemItem(
                    pedido_id=pedido.id,
                    numero=pedido.numero,
                    cliente=pedido.cliente,
                    data_entrada=pedido.data_entrada,
                    data_entrega=pedido.data_entrega,
                    status=status_str,
                    total_itens=len(items),
                    total_metragem=round(total_metragem, 4),
                    valor_total=round(valor_total, 2),
                )
            )

        return PedidoMetragemResponse(
            items=items_list,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar metragem dos pedidos: {e}")


@router.get("/producao/estatisticas", response_model=ProducaoTipoEstatisticaResponse)
async def obter_estatisticas_producao(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
):
    """
    Consolida quantidade de pedidos, total de itens, metragem e faturamento
    agrupados por tipo de produção no período especificado.
    """
    try:
        mode = date_mode.lower().strip()
        if mode not in ("entrada", "entrega"):
            raise HTTPException(status_code=400, detail="date_mode inválido. Use 'entrada' ou 'entrega'.")

        pedidos_with_items = await get_filtered_orders(
            session=session,
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=mode,
        )

        # Agrupar por tipo_producao
        stats: Dict[str, Dict[str, Any]] = {}

        for pedido, items in pedidos_with_items:
            tipos_no_pedido: Set[str] = set()
            
            for item in items:
                # Obter e normalizar tipo de produção
                tipo = (getattr(item, "tipo_producao", None) or "Sem tipo").strip().lower()
                if not tipo:
                    tipo = "sem tipo"
                
                tipos_no_pedido.add(tipo)
                
                if tipo not in stats:
                    stats[tipo] = {
                        "tipo_producao": tipo,
                        "pedidos_set": set(),
                        "total_itens": 0,
                        "total_metragem": 0.0,
                        "valor_total": 0.0,
                    }
                
                # Obter quantidade do item
                item_qty = get_item_quantity(item)
                stats[tipo]["total_itens"] += int(item_qty)
                
                # Calcular metragem total do item (metragem unitária * quantidade)
                metragem = calculate_item_consumption_meters(item) * item_qty
                stats[tipo]["total_metragem"] += metragem
                
                # Valor do item
                valor = get_item_value(item)
                stats[tipo]["valor_total"] += valor
            
            # Adicionar o ID do pedido nos sets de cada tipo encontrado nesse pedido
            for tipo in tipos_no_pedido:
                stats[tipo]["pedidos_set"].add(pedido.id)

        items_list = []
        for tipo, data in stats.items():
            items_list.append(
                ProducaoTipoEstatisticaItem(
                    tipo_producao=data["tipo_producao"],
                    total_pedidos=len(data["pedidos_set"]),
                    total_itens=data["total_itens"],
                    total_metragem=round(data["total_metragem"], 4),
                    valor_total=round(data["valor_total"], 2),
                )
            )

        # Ordenar os resultados por faturamento/metragem decrescente
        items_list.sort(key=lambda x: x.total_metragem, reverse=True)

        return ProducaoTipoEstatisticaResponse(
            items=items_list,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar estatísticas de produção: {e}")


@router.get("/producao/tecidos", response_model=ProducaoTecidoEstatisticaResponse)
async def obter_estatisticas_tecidos(
    session: AsyncSession = Depends(get_session),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    date_mode: str = Query("entrada", description="Modo de data: 'entrada' ou 'entrega'"),
    status: Optional[str] = Query(None, description="Status dos pedidos"),
):
    """
    Consolida quantidade de pedidos, total de itens e metragem
    agrupados por tipo de tecido/material no período especificado.
    """
    try:
        mode = date_mode.lower().strip()
        if mode not in ("entrada", "entrega"):
            raise HTTPException(status_code=400, detail="date_mode inválido. Use 'entrada' ou 'entrega'.")

        pedidos_with_items = await get_filtered_orders(
            session=session,
            start_date=data_inicio,
            end_date=data_fim,
            status=status,
            date_mode=mode,
        )

        # Agrupar por tecido
        stats: Dict[str, Dict[str, Any]] = {}

        for pedido, items in pedidos_with_items:
            tecidos_no_pedido: Set[str] = set()
            
            for item in items:
                # Obter e normalizar nome do tecido
                tecido = (getattr(item, "tecido", None) or "Sem tecido").strip().lower()
                if not tecido:
                    tecido = "sem tecido"
                
                # Capitalizar palavras para exibição mais limpa
                tecido_display = " ".join(word.capitalize() for word in tecido.split())
                
                tecidos_no_pedido.add(tecido_display)
                
                if tecido_display not in stats:
                    stats[tecido_display] = {
                        "tecido": tecido_display,
                        "pedidos_set": set(),
                        "total_itens": 0,
                        "total_metragem": 0.0,
                    }
                
                # Obter quantidade do item
                item_qty = get_item_quantity(item)
                stats[tecido_display]["total_itens"] += int(item_qty)
                
                # Calcular metragem total do item (metragem unitária * quantidade)
                metragem = calculate_item_consumption_meters(item) * item_qty
                stats[tecido_display]["total_metragem"] += metragem
            
            # Adicionar o ID do pedido nos sets de cada tecido encontrado nesse pedido
            for tecido_display in tecidos_no_pedido:
                stats[tecido_display]["pedidos_set"].add(pedido.id)

        items_list = []
        for tecido, data in stats.items():
            items_list.append(
                ProducaoTecidoEstatisticaItem(
                    tecido=data["tecido"],
                    total_pedidos=len(data["pedidos_set"]),
                    total_itens=data["total_itens"],
                    total_metragem=round(data["total_metragem"], 4),
                )
            )

        # Ordenar os resultados por metragem decrescente
        items_list.sort(key=lambda x: x.total_metragem, reverse=True)

        return ProducaoTecidoEstatisticaResponse(
            items=items_list,
            data_inicio=data_inicio,
            data_fim=data_fim,
            date_mode=mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar estatísticas de tecidos: {e}")


@router.get("/producao/alertas", response_model=AlertasProducaoResponse)
async def obter_alertas_producao(
    session: AsyncSession = Depends(get_session),
):
    """
    Lista alertas de produção (atrasados, urgentes não iniciados e estagnados/parados na costura/calandra).
    """
    try:
        from datetime import date, datetime, timedelta
        
        # Buscar todos os pedidos sem filtros de data, depois filtramos na lógica
        pedidos_with_items = await get_filtered_orders(
            session=session,
            status=None,
        )
        
        today = date.today()
        now_utc = datetime.utcnow()
        alertas: List[AlertaPedidoItem] = []
        
        # Mapeamento do Status para string limpa
        def get_status_str(p_status) -> str:
            return p_status.value if hasattr(p_status, "value") else str(p_status)
        
        # Função para parsear data de entrega
        def parse_delivery_date(val: Any) -> Optional[date]:
            if not val:
                return None
            if isinstance(val, date) and not isinstance(val, datetime):
                return val
            if isinstance(val, datetime):
                return val.date()
            try:
                clean = str(val).replace("Z", "").split("T")[0]
                return datetime.strptime(clean, "%Y-%m-%d").date()
            except ValueError:
                return None

        for pedido, items in pedidos_with_items:
            status_str = get_status_str(pedido.status)
            
            # Pular pedidos entregues ou cancelados
            if status_str in ("entregue", "cancelado"):
                continue
                
            delivery_date = parse_delivery_date(pedido.data_entrega)
            
            # 1. Alerta: ATRASADO (Data de entrega menor que hoje)
            if delivery_date and delivery_date < today:
                alertas.append(
                    AlertaPedidoItem(
                        pedido_id=pedido.id,
                        numero=pedido.numero,
                        cliente=pedido.cliente,
                        data_entrega=pedido.data_entrega,
                        status=status_str,
                        tipo_alerta="atrasado",
                    )
                )
                continue # Um pedido não precisa ter múltiplos alertas, priorizamos atrasado
            
            # 2. Alerta: URGENTE PENDENTE (Entrega hoje ou amanhã e status ainda é pendente)
            if (
                delivery_date 
                and today <= delivery_date <= (today + timedelta(days=1))
                and status_str == "pendente"
            ):
                alertas.append(
                    AlertaPedidoItem(
                        pedido_id=pedido.id,
                        numero=pedido.numero,
                        cliente=pedido.cliente,
                        data_entrega=pedido.data_entrega,
                        status=status_str,
                        tipo_alerta="urgente_pendente",
                    )
                )
                continue
            
            # 3. Alerta: ESTAGNADO (Status em_producao há mais de 48 horas)
            if status_str == "em_producao" and pedido.ultima_atualizacao:
                # O banco armazena como naive datetime em UTC geralmente, ou com fuso
                # Fazemos comparação naive em UTC
                last_update = pedido.ultima_atualizacao
                if last_update.tzinfo is not None:
                    last_update = last_update.replace(tzinfo=None)
                
                stuck_duration = now_utc - last_update
                hours_estagnado = int(stuck_duration.total_seconds() / 3600)
                
                if hours_estagnado >= 48:
                    alertas.append(
                        AlertaPedidoItem(
                            pedido_id=pedido.id,
                            numero=pedido.numero,
                            cliente=pedido.cliente,
                            data_entrega=pedido.data_entrega,
                            status=status_str,
                            tipo_alerta="estagnado",
                            horas_estagnado=hours_estagnado,
                        )
                    )

        # Ordenar os alertas: atrasados primeiro, depois urgentes pendentes, depois estagnados
        order_map = {"atrasado": 0, "urgente_pendente": 1, "estagnado": 2}
        alertas.sort(key=lambda x: order_map.get(x.tipo_alerta, 3))
        
        return AlertasProducaoResponse(items=alertas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar alertas de produção: {e}")

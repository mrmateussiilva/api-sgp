from typing import Optional, List, Dict, DefaultDict, Any
from datetime import datetime
from collections import Counter, defaultdict
from sqlmodel import select, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from pedidos.schema import Pedido, Status
from pedidos.service import json_string_to_items
from .schema import (
    MaterialStatsResponse, 
    MaterialStatsKPIs, 
    RankingItem,
    MaterialEvolutionResponse,
    MaterialEvolutionItem
)

from .stock_service import (
    calculate_item_consumption_meters,
    normalize_material_name,
    parse_decimal_value
)

async def get_material_stats(
    session: AsyncSession,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    tipo_producao: Optional[str] = None
) -> MaterialStatsResponse:
    # 1. Buscar pedidos
    query = select(Pedido).where(Pedido.status != Status.CANCELADO)

    # Filtros de data (baseados em data_entrada ou data_criacao?)
    # O PedidoBase tem data_entrada: str e data_criacao: Optional[datetime]
    # Vamos usar data_entrada para consistência com o que o usuário costuma filtrar
    if data_inicio:
        query = query.where(Pedido.data_entrada >= data_inicio)
    if data_fim:
        query = query.where(Pedido.data_entrada <= data_fim)

    result = await session.execute(query)
    pedidos = result.scalars().all()

    # KPIs e Contadores
    total_itens = 0
    total_area_m2 = 0.0
    total_ilhos = 0
    total_itens_com_ilhos = 0

    # MaterialBase: { "NOME": { "area": 10.5, "itens": 5 } }
    material_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"area": 0.0, "itens": 0})
    # Acabamentos: Counter (continuam unitários ou ocorrência)
    acabamento_counter: Counter[str] = Counter()

    # Filtro por tipo: { "painel": { "NOME": { "area": 5.0, "itens": 2 } } }
    material_por_tipo: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"area": 0.0, "itens": 0})
    )

    for pedido in pedidos:
        items = json_string_to_items(pedido.items or "[]")
        for item in items:
            # Filtro por tipo de produção no item (se solicitado)
            if tipo_producao and item.tipo_producao != tipo_producao:
                continue

            total_itens += 1

            # 1. Material Base (Consumo por Área)
            tecido_raw = (item.tecido or "NÃO INFORMADO").strip()
            tecido = normalize_material_name(tecido_raw).upper()

            # Cálculo de área (m²)
            area_item = calculate_item_consumption_meters(item)

            # Multiplicar pela quantidade do item (quantidade_paineis, etc)
            # Vamos tentar inferir a quantidade do item
            quantidade_item = 1.0
            for field in ['quantidade_paineis', 'quantidade_lona', 'quantidade_adesivo', 'quantidade_totem']:
                val = getattr(item, field, None)
                if val:
                    q = parse_decimal_value(val)
                    if q > 0:
                        quantidade_item = q
                        break

            total_consumo_item = area_item * quantidade_item
            total_area_m2 += total_consumo_item

            material_stats[tecido]["area"] += total_consumo_item
            material_stats[tecido]["itens"] += 1

            t_prod = item.tipo_producao or "OUTROS"
            material_por_tipo[t_prod][tecido]["area"] += total_consumo_item
            material_por_tipo[t_prod][tecido]["itens"] += 1

            # 2. Acabamentos
            # Campos: overloque, elastico, ilhos, emenda
            # acabamento é um objeto Acabamento(overloque, elastico, ilhos)
            if item.acabamento:
                if item.acabamento.overloque:
                    acabamento_counter["OVERLOQUE"] += 1
                if item.acabamento.elastico:
                    acabamento_counter["ELÁSTICO"] += 1
                if item.acabamento.ilhos:
                    acabamento_counter["ILHÓS (PRESENÇA)"] += 1

            # Outros acabamentos em campos string
            if item.emenda and item.emenda != "sem-emenda":
                acabamento_counter["EMENDA"] += 1

            # Ilhós quantitativo
            # quantidade_ilhos é string
            try:
                qtd_ilhos_val = int(item.quantidade_ilhos) if item.quantidade_ilhos else 0
                if qtd_ilhos_val > 0:
                    total_ilhos += qtd_ilhos_val
                    total_itens_com_ilhos += 1
                    acabamento_counter["ILHÓS (QUANTIDADE)"] += 1
            except (ValueError, TypeError):
                pass

    # Calcular Rankings de Materiais
    def build_material_ranking(stats_dict: Dict[str, Dict[str, Any]], total_area: float) -> List[RankingItem]:
        # Ordenar por área descendente
        sorted_stats = sorted(stats_dict.items(), key=lambda x: x[1]["area"], reverse=True)
        items = []
        for nome, data in sorted_stats[:20]:
            percent = (data["area"] / total_area * 100) if total_area > 0 else 0
            items.append(RankingItem(
                nome=nome,
                quantidade_itens=data["itens"],
                area_total_m2=round(data["area"], 2),
                percentual_area=round(percent, 2)
            ))
        return items

    # Calcular Ranking de Acabamentos (mantém ocorrência)
    def build_acabamento_ranking(counter: Counter[str], total_count: int) -> List[RankingItem]:
        items = []
        for nome, qtd in counter.most_common(20):
            percent = (qtd / total_count * 100) if total_count > 0 else 0
            items.append(RankingItem(
                nome=nome,
                quantidade_itens=qtd,
                area_total_m2=0.0, # Acabamentos não têm área diretamente associada neste contexto
                percentual_area=round(percent, 2)
            ))
        return items

    ranking_materiais = build_material_ranking(material_stats, total_area_m2)
    ranking_acabamentos = build_acabamento_ranking(acabamento_counter, total_itens)

    por_tipo_producao = {}
    for t_prod, stats in material_por_tipo.items():
        area_t_prod = sum(s["area"] for s in stats.values())
        por_tipo_producao[t_prod] = build_material_ranking(stats, area_t_prod)

    # KPIs
    material_mais_usado = ranking_materiais[0].nome if ranking_materiais else None
    acabamento_mais_usado = ranking_acabamentos[0].nome if ranking_acabamentos else None

    # Calcular Pico de Consumo
    # total_pelo_dia[data] = m2
    total_pelo_dia: Dict[str, float] = defaultdict(float)
    for pedido in pedidos:
        d = pedido.data_entrada
        items = json_string_to_items(pedido.items or "[]")
        for item in items:
            if tipo_producao and item.tipo_producao != tipo_producao:
                continue
            consumo = calculate_item_consumption_meters(item)
            q = 1.0
            for field in ['quantidade_paineis', 'quantidade_lona', 'quantidade_adesivo', 'quantidade_totem']:
                val = getattr(item, field, None)
                if val:
                    qv = parse_decimal_value(val)
                    if qv > 0:
                        q = qv
                        break
            total_pelo_dia[d] += (consumo * q)
    
    data_pico = None
    m2_pico = 0.0
    if total_pelo_dia:
        data_pico = max(total_pelo_dia, key=total_pelo_dia.get)
        m2_pico = round(float(total_pelo_dia[data_pico]), 2)

    kpis = MaterialStatsKPIs(
        total_itens=total_itens,
        total_area_m2=round(total_area_m2, 2),
        material_mais_usado=material_mais_usado,
        acabamento_mais_usado=acabamento_mais_usado,
        total_ilhos=total_ilhos,
        total_itens_com_ilhos=total_itens_com_ilhos,
        data_pico=data_pico,
        m2_pico=m2_pico
    )

    return MaterialStatsResponse(
        kpis=kpis,
        ranking_materiais=ranking_materiais,
        ranking_acabamentos=ranking_acabamentos,
        por_tipo_producao=por_tipo_producao
    )


async def get_material_evolution(
    session: AsyncSession,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    tipo_producao: Optional[str] = None
) -> MaterialEvolutionResponse:
    # 1. Buscar pedidos (mesma lógica de filtros)
    query = select(Pedido).where(Pedido.status != Status.CANCELADO)
    if data_inicio:
        query = query.where(Pedido.data_entrada >= data_inicio)
    if data_fim:
        query = query.where(Pedido.data_entrada <= data_fim)

    result = await session.execute(query)
    pedidos = result.scalars().all()

    # Estruturas para agregação
    # total_pelo_periodo[material] = m2_acumulado (para achar top 3)
    total_pelo_periodo: Counter[str] = Counter()
    
    # evolucao_diaria[data][material] = m2
    evolucao_diaria: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    diario_total: Dict[str, float] = defaultdict(float)

    for pedido in pedidos:
        data_str = pedido.data_entrada # Esperado ser YYYY-MM-DD
        items = json_string_to_items(pedido.items or "[]")
        
        for item in items:
            if tipo_producao and item.tipo_producao != tipo_producao:
                continue

            tecido_raw = (item.tecido or "NÃO INFORMADO").strip()
            tecido = normalize_material_name(tecido_raw).upper()

            area_item = calculate_item_consumption_meters(item)
            
            quantidade_item = 1.0
            for field in ['quantidade_paineis', 'quantidade_lona', 'quantidade_adesivo', 'quantidade_totem']:
                val = getattr(item, field, None)
                if val:
                    q = parse_decimal_value(val)
                    if q > 0:
                        quantidade_item = q
                        break

            consumo = area_item * quantidade_item
            
            total_pelo_periodo[tecido] += consumo
            evolucao_diaria[data_str][tecido] += consumo
            diario_total[data_str] += consumo

    # 2. Identificar Top 3 materiais
    top_3_materiais = [nome for nome, _ in total_pelo_periodo.most_common(3)]
    
    # 3. Formatar evolução diária
    # Ordenar datas
    datas_ordenadas = sorted(evolucao_diaria.keys())
    
    items_evolucao = []
    for data in datas_ordenadas:
        top_mats_dia = {}
        for mat in top_3_materiais:
            top_mats_dia[mat] = round(evolucao_diaria[data][mat], 2)
            
        items_evolucao.append(MaterialEvolutionItem(
            data=data,
            total=round(diario_total[data], 2),
            top_materiais=top_mats_dia
        ))

    if not items_evolucao and data_fim:
        items_evolucao.append(MaterialEvolutionItem(
            data=data_fim,
            total=0.0,
            top_materiais={}
        ))

    return MaterialEvolutionResponse(
        top_3_nomes=top_3_materiais,
        evolucao=items_evolucao
    )

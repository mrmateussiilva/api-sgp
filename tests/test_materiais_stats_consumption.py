import pytest
from sqlmodel import Session, select
from datetime import datetime
from materiais.stats_service import get_material_stats
from pedidos.schema import Pedido, InternalStatus, Status
import json

@pytest.mark.asyncio
async def test_material_consumption_area_calculation(db_session):
    # Criar um pedido com itens de diferentes tamanhos
    # Item 1: TACTEL 2m x 3m x 2 unidades = 12m2
    # Item 2: OXFORDINE 1m x 1m x 1 unidade = 1m2
    # Item 3: TACTEL 1m x 1m x 1 unidade = 1m2 -> Total TACTEL = 13m2
    
    item1 = {
        "tipo_producao": "painel",
        "tecido": "TACTEL",
        "largura": "2.0",
        "altura": "3.0",
        "quantidade_paineis": "2"
    }
    item2 = {
        "tipo_producao": "painel",
        "tecido": "OXFORDINE",
        "largura": "1.0",
        "altura": "1.0",
        "quantidade_paineis": "1"
    }
    item3 = {
        "tipo_producao": "painel",
        "tecido": "TACTEL",
        "largura": "1.0",
        "altura": "1.0",
        "quantidade_paineis": "1"
    }
    
    pedido = Pedido(
        numero="TEST001",
        data_entrada=datetime.now().strftime("%Y-%m-%d"),
        cliente="Test Customer",
        status=Status.PENDENTE,
        items=json.dumps([item1, item2, item3])
    )
    
    db_session.add(pedido)
    await db_session.commit()
    
    stats = await get_material_stats(db_session)
    
    # Validar KPIs
    assert stats.kpis.total_itens == 3
    assert stats.kpis.total_area_m2 == 14.0 # 12 + 1 + 1
    assert stats.kpis.material_mais_usado == "TACTEL"
    
    # Validar Ranking
    tactel_ranking = next(r for r in stats.ranking_materiais if r.nome == "TACTEL")
    assert tactel_ranking.area_total_m2 == 13.0
    assert tactel_ranking.quantidade_itens == 2
    
    oxfordine_ranking = next(r for r in stats.ranking_materiais if r.nome == "OXFORDINE")
    assert oxfordine_ranking.area_total_m2 == 1.0
    assert oxfordine_ranking.quantidade_itens == 1

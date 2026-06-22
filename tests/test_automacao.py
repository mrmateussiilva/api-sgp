import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_automacao_pedidos_metragem(client: AsyncClient, clean_db):
    """Testa o endpoint de metragem de pedidos."""
    # Criar um pedido com 2 itens com metragens diferentes
    pedido_data = {
        "cliente": "Cliente Automação 1",
        "data_entrada": "2026-06-15",
        "data_entrega": "2026-06-18",
        "items": [
            {
                "tipo_producao": "painel",
                "descricao": "Painel Grande",
                "largura": "3.0",
                "altura": "2.0",
                "quantidade_paineis": "2", # Quantidade = 2
                "valor_unitario": "150.00"
            },
            {
                "tipo_producao": "lona",
                "descricao": "Lona Pequena",
                "largura": "1.0",
                "altura": "1.0",
                "quantidade_lona": "1", # Quantidade = 1
                "valor_unitario": "50.00"
            }
        ]
    }
    
    resp_create = await client.post("/pedidos/", json=pedido_data)
    assert resp_create.status_code == 200
    
    # Chamar endpoint de metragem
    response = await client.get("/automacao/pedidos/metragem")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    
    item = data["items"][0]
    assert item["cliente"] == "Cliente Automação 1"
    assert item["total_itens"] == 2
    # Metragem esperada: (3.0 * 2.0 * 2) + (1.0 * 1.0 * 1) = 12.0 + 1.0 = 13.0
    assert float(item["total_metragem"]) == 13.0


@pytest.mark.asyncio
async def test_automacao_producao_estatisticas(client: AsyncClient, clean_db):
    """Testa o endpoint de estatísticas de produção."""
    # Criar pedido 1
    pedido1 = {
        "cliente": "Cliente Automação A",
        "data_entrada": "2026-06-15",
        "items": [
            {
                "tipo_producao": "painel",
                "descricao": "Painel A",
                "largura": "2.0",
                "altura": "2.0",
                "quantidade_paineis": "1", # Area = 4.0
                "valor_unitario": "100.00"
            }
        ]
    }
    # Criar pedido 2
    pedido2 = {
        "cliente": "Cliente Automação B",
        "data_entrada": "2026-06-16",
        "items": [
            {
                "tipo_producao": "painel",
                "descricao": "Painel B",
                "largura": "2.0",
                "altura": "2.0",
                "quantidade_paineis": "1", # Area = 4.0
                "valor_unitario": "100.00"
            },
            {
                "tipo_producao": "adesivo",
                "descricao": "Adesivo B",
                "largura": "1.0",
                "altura": "1.0",
                "quantidade_adesivo": "3", # Area = 3.0
                "valor_unitario": "10.00"
            }
        ]
    }
    
    await client.post("/pedidos/", json=pedido1)
    await client.post("/pedidos/", json=pedido2)
    
    # Chamar endpoint de estatísticas
    response = await client.get("/automacao/producao/estatisticas")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    
    # Deve conter painel e adesivo
    items = data["items"]
    assert len(items) == 2
    
    # Como ordena por metragem decrescente, painel deve vir primeiro (4.0 * 1 + 4.0 * 1 = 8.0) contra adesivo (1.0 * 3 = 3.0)
    assert items[0]["tipo_producao"] == "painel"
    assert items[0]["total_pedidos"] == 2
    assert items[0]["total_itens"] == 2
    assert float(items[0]["total_metragem"]) == 8.0
    
    assert items[1]["tipo_producao"] == "adesivo"
    assert items[1]["total_pedidos"] == 1
    assert items[1]["total_itens"] == 3
    assert float(items[1]["total_metragem"]) == 3.0


@pytest.mark.asyncio
async def test_automacao_producao_tecidos(client: AsyncClient, clean_db):
    """Testa o endpoint de estatísticas de tecidos."""
    pedido = {
        "cliente": "Cliente Tecidos",
        "data_entrada": "2026-06-15",
        "items": [
            {
                "tipo_producao": "painel",
                "tecido": "oxford",
                "largura": "2.0",
                "altura": "2.0",
                "quantidade_paineis": "2", # Area = 8.0 Oxford
                "valor_unitario": "50.00"
            },
            {
                "tipo_producao": "painel",
                "tecido": "tactel",
                "largura": "1.0",
                "altura": "1.0",
                "quantidade_paineis": "1", # Area = 1.0 Tactel
                "valor_unitario": "20.00"
            }
        ]
    }
    
    await client.post("/pedidos/", json=pedido)
    
    response = await client.get("/automacao/producao/tecidos")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    items = data["items"]
    assert len(items) == 2
    
    # Ordenado por metragem decrescente (Oxford 8.0m² primeiro, depois Tactel 1.0m²)
    assert items[0]["tecido"] == "Oxford"
    assert float(items[0]["total_metragem"]) == 8.0
    assert items[0]["total_itens"] == 2
    
    assert items[1]["tecido"] == "Tactel"
    assert float(items[1]["total_metragem"]) == 1.0
    assert items[1]["total_itens"] == 1


@pytest.mark.asyncio
async def test_automacao_producao_alertas(client: AsyncClient, clean_db, test_session):
    """Testa o endpoint de alertas de produção."""
    from datetime import date, datetime, timedelta
    from sqlalchemy import text
    from pedidos.schema import Pedido
    
    # 1. Criar pedido Atrasado (data de entrega ontem, pendente)
    data_ontem = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    pedido_atrasado = {
        "cliente": "Cliente Atrasado",
        "data_entrada": "2026-06-15",
        "data_entrega": data_ontem,
        "status": "pendente",
        "items": []
    }
    
    # 2. Criar pedido Urgente (data de entrega hoje, pendente)
    data_hoje = date.today().strftime("%Y-%m-%d")
    pedido_urgente = {
        "cliente": "Cliente Urgente",
        "data_entrada": "2026-06-15",
        "data_entrega": data_hoje,
        "status": "pendente",
        "items": []
    }
    
    # 3. Criar pedido Estagnado (status em_producao, entrega no futuro, ultima_atualizacao 3 dias atrás)
    data_futura = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    pedido_estagnado = {
        "cliente": "Cliente Estagnado",
        "data_entrada": "2026-06-15",
        "data_entrega": data_futura,
        "status": "em_producao",
        "items": []
    }
    
    resp_atr = await client.post("/pedidos/", json=pedido_atrasado)
    resp_urg = await client.post("/pedidos/", json=pedido_urgente)
    resp_est = await client.post("/pedidos/", json=pedido_estagnado)
    
    id_estagnado = resp_est.json()["id"]
    
    # Alterar ultima_atualizacao no banco para 3 dias atrás
    tres_dias_atras = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    await test_session.execute(
        text("UPDATE pedidos SET ultima_atualizacao = :data WHERE id = :id"),
        {"data": tres_dias_atras, "id": id_estagnado}
    )
    await test_session.commit()
    
    # Chamar endpoint de alertas
    response = await client.get("/automacao/producao/alertas")
    assert response.status_code == 200
    
    data = response.json()
    assert "items" in data
    items = data["items"]
    
    # Deve encontrar os 3 alertas
    assert len(items) == 3
    
    tipos_alertas = [item["tipo_alerta"] for item in items]
    assert "atrasado" in tipos_alertas
    assert "urgente_pendente" in tipos_alertas
    assert "estagnado" in tipos_alertas
    
    # Verificar horas de estagnação (deve ser em torno de 72 horas)
    for item in items:
        if item["tipo_alerta"] == "estagnado":
            assert item["horas_estagnado"] >= 70


"""
Testes para endpoints de pedidos.
Cobre criação, listagem, atualização, deleção e filtros.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime
import pedidos.router
from pedidos.schema import Status, ItemPedido, Acabamento


@pytest.mark.asyncio
async def test_criar_pedido_sucesso(client: AsyncClient, clean_db):
    """Testa criação de pedido com sucesso."""
    # Resetar contador global
    initial_id = pedidos.router.ULTIMO_PEDIDO_ID
    
    pedido_data = {
        "cliente": "João Silva",
        "telefone_cliente": "11999999999",
        "data_entrada": "2024-01-15",
        "data_entrega": "2024-01-20",
        "valor_total": "1000.00",
        "valor_itens": "900.00",
        "valor_frete": "100.00",
        "items": [
            {
                "tipo_producao": "painel",
                "descricao": "Painel promocional",
                "largura": "2.0",
                "altura": "1.5",
                "metro_quadrado": "3.0",
                "vendedor": "Maria",
                "designer": "Pedro",
                "tecido": "Banner",
                "valor_unitario": "300.00"
            }
        ]
    }
    
    response = await client.post("/pedidos", json=pedido_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verificar que o pedido foi criado
    assert data["id"] is not None
    assert data["cliente"] == "João Silva"
    assert len(data["items"]) == 1
    assert data["items"][0]["descricao"] == "Painel promocional"
    
    # Verificar que ULTIMO_PEDIDO_ID foi incrementado
    assert pedidos.router.ULTIMO_PEDIDO_ID > initial_id


@pytest.mark.asyncio
async def test_criar_pedido_incrementa_id(client: AsyncClient, clean_db):
    """Testa que cada novo pedido recebe um ID crescente."""
    pedidos.router.ULTIMO_PEDIDO_ID = 0
    
    pedido_base = {
        "cliente": "Cliente Teste",
        "data_entrada": "2024-01-15",
        "items": []
    }
    
    # Criar primeiro pedido
    response1 = await client.post("/pedidos", json=pedido_base)
    assert response1.status_code == 200
    id1 = response1.json()["id"]
    
    # Criar segundo pedido
    pedido_base["cliente"] = "Cliente Teste 2"
    response2 = await client.post("/pedidos", json=pedido_base)
    assert response2.status_code == 200
    id2 = response2.json()["id"]
    
    # IDs devem ser sequenciais
    assert id2 > id1


@pytest.mark.asyncio
async def test_listar_pedidos(client: AsyncClient, clean_db):
    """Testa listagem de pedidos."""
    # Criar alguns pedidos
    for i in range(3):
        await client.post("/pedidos", json={
            "cliente": f"Cliente {i}",
            "data_entrada": "2024-01-15",
            "items": []
        })
    
    response = await client.get("/pedidos")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    assert all("id" in pedido for pedido in data)
    assert all("cliente" in pedido for pedido in data)


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_cliente(client: AsyncClient, clean_db):
    """Testa filtro por nome do cliente."""
    # Criar pedidos com clientes diferentes
    await client.post("/pedidos", json={
        "cliente": "João Silva",
        "data_entrada": "2024-01-15",
        "items": []
    })
    await client.post("/pedidos", json={
        "cliente": "Maria Santos",
        "data_entrada": "2024-01-15",
        "items": []
    })
    
    # Filtrar por "João"
    response = await client.get("/pedidos?cliente=João")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert "João" in data[0]["cliente"]


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_data(client: AsyncClient, clean_db):
    """Testa filtro por data de entrada."""
    # Criar pedidos em datas diferentes
    await client.post("/pedidos", json={
        "cliente": "Cliente 1",
        "data_entrada": "2024-01-15",
        "items": []
    })
    await client.post("/pedidos", json={
        "cliente": "Cliente 2",
        "data_entrada": "2024-01-20",
        "items": []
    })
    
    # Filtrar por período
    response = await client.get("/pedidos?data_inicio=2024-01-15&data_fim=2024-01-16")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["data_entrada"] == "2024-01-15"


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_status(client: AsyncClient, clean_db):
    """Testa filtro por status."""
    # Criar pedidos com status diferentes
    await client.post("/pedidos", json={
        "cliente": "Cliente 1",
        "data_entrada": "2024-01-15",
        "status": "pendente",
        "items": []
    })
    await client.post("/pedidos", json={
        "cliente": "Cliente 2",
        "data_entrada": "2024-01-15",
        "status": "em_producao",
        "items": []
    })
    
    # Filtrar por status pendente
    response = await client.get("/pedidos?status=pendente")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["status"] == "pendente"


@pytest.mark.asyncio
async def test_obter_pedido_por_id(client: AsyncClient, clean_db):
    """Testa obter pedido específico por ID."""
    # Criar pedido
    create_response = await client.post("/pedidos", json={
        "cliente": "Cliente Teste",
        "data_entrada": "2024-01-15",
        "items": [{"descricao": "Item teste"}]
    })
    pedido_id = create_response.json()["id"]
    
    # Obter pedido
    response = await client.get(f"/pedidos/{pedido_id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == pedido_id
    assert data["cliente"] == "Cliente Teste"
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_obter_pedido_inexistente(client: AsyncClient, clean_db):
    """Testa erro ao obter pedido que não existe."""
    response = await client.get("/pedidos/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_atualizar_pedido(client: AsyncClient, clean_db):
    """Testa atualização de pedido."""
    # Criar pedido
    create_response = await client.post("/pedidos", json={
        "cliente": "Cliente Original",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]
    
    # Atualizar pedido
    update_data = {
        "cliente": "Cliente Atualizado",
        "valor_total": "500.00"
    }
    response = await client.patch(f"/pedidos/{pedido_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    
    assert data["cliente"] == "Cliente Atualizado"
    assert data["valor_total"] == "500.00"


@pytest.mark.asyncio
async def test_deletar_pedido(client: AsyncClient, clean_db):
    """Testa deleção de pedido."""
    # Criar pedido
    create_response = await client.post("/pedidos", json={
        "cliente": "Cliente Para Deletar",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]
    
    # Deletar pedido
    response = await client.delete(f"/pedidos/{pedido_id}")
    assert response.status_code == 200
    
    # Verificar que foi deletado
    get_response = await client.get(f"/pedidos/{pedido_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_pedido_com_items_complexos(client: AsyncClient, clean_db):
    """Testa criação de pedido com items complexos (acabamento, etc)."""
    pedido_data = {
        "cliente": "Cliente Complexo",
        "data_entrada": "2024-01-15",
        "items": [
            {
                "tipo_producao": "painel",
                "descricao": "Painel com acabamento",
                "largura": "2.0",
                "altura": "1.5",
                "acabamento": {
                    "overloque": True,
                    "elastico": False,
                    "ilhos": True
                },
                "valor_unitario": "300.00"
            }
        ]
    }
    
    response = await client.post("/pedidos", json=pedido_data)
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["acabamento"] is not None
    assert item["acabamento"]["overloque"] is True
    assert item["acabamento"]["ilhos"] is True


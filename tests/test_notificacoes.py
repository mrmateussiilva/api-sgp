"""
Testes para endpoints de notificações.
Verifica que o ultimo_id é retornado corretamente e muda após criar pedidos.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime
import pedidos.router


@pytest.mark.asyncio
async def test_ultimas_notificacoes_retorna_ultimo_id(client: AsyncClient, clean_db):
    """Testa que o endpoint retorna o ultimo_id correto."""
    pedidos.router.ULTIMO_PEDIDO_ID = 0
    
    response = await client.get("/api/notificacoes/ultimos")
    assert response.status_code == 200
    data = response.json()
    
    assert "ultimo_id" in data
    assert "timestamp" in data
    assert data["ultimo_id"] == 0


@pytest.mark.asyncio
async def test_ultimo_id_muda_apos_criar_pedido(client: AsyncClient, clean_db):
    """Testa que o ultimo_id muda após criar um novo pedido."""
    pedidos.router.ULTIMO_PEDIDO_ID = 0
    
    # Obter ultimo_id inicial
    response1 = await client.get("/api/notificacoes/ultimos")
    initial_id = response1.json()["ultimo_id"]
    
    # Criar um pedido
    await client.post("/pedidos", json={
        "cliente": "Cliente Teste",
        "data_entrada": "2024-01-15",
        "items": []
    })
    
    # Verificar que ultimo_id mudou
    response2 = await client.get("/api/notificacoes/ultimos")
    new_id = response2.json()["ultimo_id"]
    
    assert new_id > initial_id


@pytest.mark.asyncio
async def test_timestamp_valido_iso8601(client: AsyncClient, clean_db):
    """Testa que o timestamp retornado está em formato ISO8601 válido."""
    response = await client.get("/api/notificacoes/ultimos")
    assert response.status_code == 200
    data = response.json()
    
    timestamp_str = data["timestamp"]
    
    # Tentar fazer parse do timestamp ISO8601
    try:
        datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        assert True
    except ValueError:
        pytest.fail(f"Timestamp inválido: {timestamp_str}")


@pytest.mark.asyncio
async def test_ultimo_id_incrementa_sequencialmente(client: AsyncClient, clean_db):
    """Testa que o ultimo_id incrementa sequencialmente a cada pedido criado."""
    pedidos.router.ULTIMO_PEDIDO_ID = 0
    
    # Criar 3 pedidos
    for i in range(3):
        await client.post("/pedidos", json={
            "cliente": f"Cliente {i}",
            "data_entrada": "2024-01-15",
            "items": []
        })
        
        response = await client.get("/api/notificacoes/ultimos")
        current_id = response.json()["ultimo_id"]
        
        assert current_id == (i + 1)


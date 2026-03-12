import pytest
from datetime import datetime
from httpx import AsyncClient
from typing import Dict, Any

@pytest.mark.asyncio
async def test_marcar_financeiro_grava_timestamp(client: AsyncClient, auth_headers: Dict[str, str]):
    # 1. Criar um pedido com financeiro=False
    pedido_data = {
        "cliente": "Teste Liberação 1",
        "data_entrada": datetime.utcnow().isoformat(),
        "valor_total": "100.00",
        "items": [],
        "financeiro": False
    }
    response = await client.post("/pedidos/", json=pedido_data, headers=auth_headers)
    assert response.status_code == 200
    pedido = response.json()
    pedido_id = pedido["id"]
    assert pedido["financeiro"] is False
    assert pedido["financeiro_liberado_em"] is None

    # 2. Marcar como financeiro=True via PATCH
    update_data = {"financeiro": True}
    response = await client.patch(f"/pedidos/{pedido_id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    pedido_updated = response.json()
    
    assert pedido_updated["financeiro"] is True
    assert pedido_updated["financeiro_liberado_em"] is not None
    # Verificar se é um timestamp válido
    liberado_em = datetime.fromisoformat(pedido_updated["financeiro_liberado_em"].replace('Z', '+00:00'))
    assert isinstance(liberado_em, datetime)

@pytest.mark.asyncio
async def test_desmarcar_financeiro_limpa_timestamp(client: AsyncClient, auth_headers: Dict[str, str]):
    # 1. Criar um pedido já com financeiro=True
    pedido_data = {
        "cliente": "Teste Liberação 2",
        "data_entrada": datetime.utcnow().isoformat(),
        "valor_total": "100.00",
        "items": [],
        "financeiro": True
    }
    response = await client.post("/pedidos/", json=pedido_data, headers=auth_headers)
    assert response.status_code == 200
    pedido = response.json()
    pedido_id = pedido["id"]
    assert pedido["financeiro"] is True
    assert pedido["financeiro_liberado_em"] is not None

    # 2. Desmarcar financeiro=False
    update_data = {"financeiro": False}
    response = await client.patch(f"/pedidos/{pedido_id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    pedido_updated = response.json()
    
    assert pedido_updated["financeiro"] is False
    assert pedido_updated["financeiro_liberado_em"] is None

@pytest.mark.asyncio
async def test_nao_alterar_timestamp_se_financeiro_nao_mudar(client: AsyncClient, auth_headers: Dict[str, str]):
    # 1. Criar pedido liberado
    pedido_data = {
        "cliente": "Teste Liberação 3",
        "data_entrada": datetime.utcnow().isoformat(),
        "financeiro": True,
        "items": []
    }
    response = await client.post("/pedidos/", json=pedido_data, headers=auth_headers)
    pedido = response.json()
    first_timestamp = pedido["financeiro_liberado_em"]
    
    # 2. Atualizar outro campo (ex: observacao) sem mexer no financeiro
    import asyncio
    await asyncio.sleep(1) # Garantir que se mudasse o timestamp, seria diferente
    
    update_data = {"observacao": "Mudando apenas obs"}
    response = await client.patch(f"/pedidos/{pedido['id']}", json=update_data, headers=auth_headers)
    pedido_updated = response.json()
    
    assert pedido_updated["financeiro_liberado_em"] == first_timestamp
    assert pedido_updated["observacao"] == "Mudando apenas obs"

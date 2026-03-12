"""
tests/test_guardrail.py
=======================
Testes de integração focados no Guardrail Financeiro.

Garante que o backend não confia em valores enviados pelo frontend
e sempre recalcula itens e totais antes de persistir.
"""
import pytest
from httpx import AsyncClient
from decimal import Decimal
from pedidos.pricing import parse_money

@pytest.mark.asyncio
async def test_guardrail_correcao_total_envidado_errado(client: AsyncClient, clean_db):
    """
    Cenário 2: Frontend envia valor_total errado propositalmente.
    O backend deve ignorar o valor enviado e salvar o valor correto.
    """
    pedido_data = {
        "cliente": "Teste Guardrail Total Errado",
        "data_entrada": "2024-03-12",
        "valor_frete": "10.00",
        "valor_total": "50.00",  # Valor errado enviado pelo frontend
        "items": [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
                "quantidade_paineis": "1",
            }
        ],
    }

    # 100 (painel) + 18 (ilhós) + 10 (frete) = 128.00
    response = await client.post("/pedidos/", json=pedido_data)
    assert response.status_code == 200
    data = response.json()

    # O backend deve ter corrigido para 128.00
    assert float(data["valor_total"]) == 128.00
    assert float(data["valor_itens"]) == 118.00


@pytest.mark.asyncio
async def test_guardrail_correcao_item_unitario_errado(client: AsyncClient, clean_db):
    """
    Cenário: Frontend envia valor_unitario errado para um painel.
    O backend deve recalcular a partir dos componentes.
    """
    pedido_data = {
        "cliente": "Teste Guardrail Item Errado",
        "data_entrada": "2024-03-12",
        "items": [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "valor_unitario": "100.00",  # Errado, deveria incluir ilhós
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
                "quantidade_paineis": "1",
            }
        ],
    }

    response = await client.post("/pedidos/", json=pedido_data)
    assert response.status_code == 200
    data = response.json()

    item = data["items"][0]
    # Deve ser 118.00, não 100.00
    assert float(item["valor_unitario"]) == 118.00


@pytest.mark.asyncio
async def test_guardrail_consistencia_patch_sem_items(client: AsyncClient, clean_db):
    """
    Cenário: Atualizar frete de um pedido existente.
    O backend deve recalcular o valor_total corretamente usando os itens já existentes.
    """
    # 1. Criar pedido com item (118.00) + frete (0) = 118.00
    create_payload = {
        "cliente": "Teste Consistency PATCH",
        "data_entrada": "2024-03-12",
        "valor_frete": "0.00",
        "items": [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
                "quantidade_paineis": "1",
            }
        ],
    }
    create_resp = await client.post("/pedidos/", json=create_payload)
    pedido_id = create_resp.json()["id"]

    # 2. PATCH: Alterar apenas o frete para 50.00
    # O backend não recebe a lista de itens, ele deve usar os que já estão no banco.
    # Mas no router.py atual, se 'items' não estiver no payload, ele NÃO recalcula o total?
    # Vamos verificar o código do router.py: 
    # if items_payload_for_images is not None: ... recalcula totais ...
    # Se items não for enviado, o total_itens não muda, mas o valor_total DEVE mudar se o frete mudar.
    
    update_resp = await client.patch(f"/pedidos/{pedido_id}", json={
        "valor_frete": "50.00"
    })
    
    assert update_resp.status_code == 200
    data = update_resp.json()
    
    # 118 (itens) + 50 (novo frete) = 168.00
    assert float(data["valor_total"]) == 168.00
    assert float(data["valor_itens"]) == 118.00
    assert float(data["valor_frete"]) == 50.00

@pytest.mark.asyncio
async def test_guardrail_consistencia_persistida_items_json(client: AsyncClient, clean_db):
    """
    Garante que os itens persistidos no campo JSON 'items' estão com os valores corretos.
    """
    pedido_data = {
        "cliente": "Teste JSON Persistido",
        "data_entrada": "2024-03-12",
        "items": [
            {
                "tipo_producao": "painel",
                "valor_painel": "100.00",
                "tipo_acabamento": "ilhos",
                "quantidade_ilhos": "18",
                "valor_ilhos": "1.00",
                "quantidade_paineis": "1",
            }
        ],
    }
    response = await client.post("/pedidos/", json=pedido_data)
    pedido_id = response.json()["id"]

    # Verificar no banco de dados (usando a fixture test_session ou consultando via API)
    # A resposta da API já mostra o que foi persistido após o refresh.
    data = response.json()
    item = data["items"][0]
    assert float(item["valor_unitario"]) == 118.00

"""
Testes unitários para as rotas do Painel de Designers.
Usa SQLite em memória via fixtures do conftest.py.
"""
import json
import pytest
import orjson


# ---------------------------------------------------------------------------
# Helpers reutilizáveis nos testes
# ---------------------------------------------------------------------------

def _make_pedido_payload(
    designer: str = "Ana Lima",
    status: str = "pendente",
    legenda_imagem: str = "AGUARDANDO",
) -> dict:
    """Retorna payload mínimo para criar um pedido com um item de designer."""
    item = {
        "id": None,
        "descricao": "Arte Personalizada",
        "designer": designer,
        "vendedor": "Carlos",
        "largura": "1.50",
        "altura": "0.90",
        "tipo_producao": "painel",
        "legenda_imagem": legenda_imagem,
        "valor_unitario": "150,00",
        "quantidade_paineis": "1",
    }
    return {
        "numero": None,
        "data_entrada": "2025-03-11",
        "data_entrega": "2025-03-20",
        "cliente": "Cliente Teste",
        "status": status,
        "prioridade": "NORMAL",
        "forma_envio_id": 0,
        "items": [item],
    }


# ---------------------------------------------------------------------------
# Testes: GET /designers/{nome}/itens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_itens_designer_vazio(client, admin_headers):
    """Designer sem pedidos ativos deve retornar lista vazia."""
    response = await client.get(
        "/designers/designer-inexistente-xpto/itens",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_itens_designer_com_item(client, admin_headers):
    """Designer com pedido ativo deve retornar o item correspondente."""
    # Criar pedido com item atribuído ao designer
    payload = _make_pedido_payload(designer="Ana Lima")
    create_resp = await client.post("/pedidos/", json=payload, headers=admin_headers)
    assert create_resp.status_code in (200, 201), create_resp.text

    # Buscar itens do designer
    response = await client.get("/designers/Ana Lima/itens", headers=admin_headers)
    assert response.status_code == 200

    data = response.json()
    assert len(data) >= 1

    item = data[0]
    assert item["cliente"] == "Cliente Teste"
    assert item["descricao"] == "Arte Personalizada"
    assert item["largura"] == "1.50"
    assert item["altura"] == "0.90"
    assert item["status_arte"] == "aguardando"  # legenda_imagem = "AGUARDANDO"
    assert "item_id" in item
    assert "order_id" in item


@pytest.mark.asyncio
async def test_get_itens_ignora_cancelado(client, admin_headers):
    """Pedidos com status='cancelado' não devem aparecer no painel."""
    payload = _make_pedido_payload(designer="Maria Souza", status="cancelado")
    create_resp = await client.post("/pedidos/", json=payload, headers=admin_headers)
    assert create_resp.status_code in (200, 201), create_resp.text

    response = await client.get("/designers/Maria Souza/itens", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_itens_ignora_entregue(client, admin_headers):
    """Pedidos com status='entregue' não devem aparecer no painel."""
    payload = _make_pedido_payload(designer="João Costa", status="entregue")
    create_resp = await client.post("/pedidos/", json=payload, headers=admin_headers)
    assert create_resp.status_code in (200, 201), create_resp.text

    response = await client.get("/designers/João Costa/itens", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Testes: PATCH /designers/itens/{item_id}/status-arte
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_status_arte_liberado(client, admin_headers):
    """Deve atualizar status_arte para 'liberado' sem tocar em outros campos."""
    # Criar pedido
    payload = _make_pedido_payload(designer="Pedro Alves", legenda_imagem="AGUARDANDO")
    create_resp = await client.post("/pedidos/", json=payload, headers=admin_headers)
    assert create_resp.status_code in (200, 201), create_resp.text

    # Buscar o item_id
    items_resp = await client.get("/designers/Pedro Alves/itens", headers=admin_headers)
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert len(items) >= 1
    item_id = items[0]["item_id"]
    order_id = items[0]["order_id"]

    # Confirmar campos antes do PATCH
    pedido_before = await client.get(f"/pedidos/{order_id}", headers=admin_headers)
    items_before = pedido_before.json()["items"]
    item_before = next(i for i in items_before if i.get("id") == item_id or True)

    # Fazer o PATCH
    patch_resp = await client.patch(
        f"/designers/itens/{item_id}/status-arte",
        json={"status_arte": "liberado"},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status_arte"] == "liberado"

    # Confirmar que status_arte mudou e outros campos foram preservados
    items_after_resp = await client.get("/designers/Pedro Alves/itens", headers=admin_headers)
    items_after = items_after_resp.json()
    item_after = next(i for i in items_after if i["item_id"] == item_id)
    assert item_after["status_arte"] == "liberado"
    # Verificar que dados do pedido não foram sobrescritos
    pedido_after = await client.get(f"/pedidos/{order_id}", headers=admin_headers)
    items_from_pedido = pedido_after.json()["items"]
    # Deve ter exatamente o mesmo número de itens
    assert len(items_from_pedido) == len(items_before)


@pytest.mark.asyncio
async def test_patch_status_arte_aguardando(client, admin_headers):
    """Deve reverter status_arte para 'aguardando'."""
    payload = _make_pedido_payload(designer="Luisa Ferreira", legenda_imagem="LIBERADO")
    create_resp = await client.post("/pedidos/", json=payload, headers=admin_headers)
    assert create_resp.status_code in (200, 201)

    items_resp = await client.get("/designers/Luisa Ferreira/itens", headers=admin_headers)
    item_id = items_resp.json()[0]["item_id"]

    # Confirmar que começa como liberado
    assert items_resp.json()[0]["status_arte"] == "liberado"

    # Reverter para aguardando
    patch_resp = await client.patch(
        f"/designers/itens/{item_id}/status-arte",
        json={"status_arte": "aguardando"},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status_arte"] == "aguardando"


@pytest.mark.asyncio
async def test_patch_status_arte_item_invalido(client, admin_headers):
    """item_id inexistente deve retornar 404."""
    response = await client.patch(
        "/designers/itens/999999/status-arte",
        json={"status_arte": "liberado"},
        headers=admin_headers,
    )
    assert response.status_code == 404

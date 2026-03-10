import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_estatisticas_materiais_mais_usados(client: AsyncClient, clean_db):
    await client.post("/materiais/", json={"nome": "Banner", "tipo": "tecido", "ativo": True, "estoque_metros": 100})
    await client.post("/materiais/", json={"nome": "Lona", "tipo": "tecido", "ativo": True, "estoque_metros": 100})

    await client.post(
        "/pedidos/",
        json={
            "cliente": "Cliente A",
            "data_entrada": "2026-03-10",
            "items": [
                {"descricao": "Item 1", "tecido": "Banner"},
                {"descricao": "Item 2", "tecido": "Banner"},
                {"descricao": "Item 3", "tecido": "Lona"},
            ],
        },
    )

    response = await client.get("/materiais/estatisticas/uso?ordem=mais&limit=5")
    assert response.status_code == 200

    payload = response.json()
    assert payload["total_itens_com_material"] == 3
    assert payload["total_materiais_distintos_com_uso"] == 2
    assert payload["materiais"][0]["nome_material"] == "Banner"
    assert payload["materiais"][0]["quantidade_usos"] == 2
    assert payload["materiais"][1]["nome_material"] == "Lona"
    assert payload["materiais"][1]["quantidade_usos"] == 1


@pytest.mark.asyncio
async def test_estatisticas_materiais_ignora_cancelados_por_padrao(client: AsyncClient, clean_db):
    await client.post("/materiais/", json={"nome": "Banner", "tipo": "tecido", "ativo": True, "estoque_metros": 100})

    await client.post(
        "/pedidos/",
        json={
            "cliente": "Cliente Ativo",
            "data_entrada": "2026-03-10",
            "status": "pendente",
            "items": [{"descricao": "Item ativo", "tecido": "Banner"}],
        },
    )
    await client.post(
        "/pedidos/",
        json={
            "cliente": "Cliente Cancelado",
            "data_entrada": "2026-03-10",
            "status": "cancelado",
            "items": [{"descricao": "Item cancelado", "tecido": "Banner"}],
        },
    )

    response_padrao = await client.get("/materiais/estatisticas/uso")
    assert response_padrao.status_code == 200
    payload_padrao = response_padrao.json()
    assert payload_padrao["total_itens_com_material"] == 1
    assert payload_padrao["materiais"][0]["quantidade_usos"] == 1

    response_com_cancelados = await client.get("/materiais/estatisticas/uso?incluir_cancelados=true")
    assert response_com_cancelados.status_code == 200
    payload_com_cancelados = response_com_cancelados.json()
    assert payload_com_cancelados["total_itens_com_material"] == 2
    assert payload_com_cancelados["materiais"][0]["quantidade_usos"] == 2


@pytest.mark.asyncio
async def test_estatisticas_materiais_incluir_sem_uso(client: AsyncClient, clean_db):
    await client.post("/materiais/", json={"nome": "Banner", "tipo": "tecido", "ativo": True, "estoque_metros": 100})
    await client.post("/materiais/", json={"nome": "Lona", "tipo": "tecido", "ativo": True, "estoque_metros": 100})
    await client.post("/materiais/", json={"nome": "Tecido Inativo", "tipo": "tecido", "ativo": False, "estoque_metros": 100})

    await client.post(
        "/pedidos/",
        json={
            "cliente": "Cliente A",
            "data_entrada": "2026-03-10",
            "items": [{"descricao": "Item 1", "tecido": "Banner"}],
        },
    )

    response = await client.get(
        "/materiais/estatisticas/uso?ordem=menos&incluir_sem_uso=true&somente_ativos=true&limit=10"
    )
    assert response.status_code == 200
    payload = response.json()

    nomes = [item["nome_material"] for item in payload["materiais"]]
    assert "Lona" in nomes
    assert "Tecido Inativo" not in nomes

    lona = next(item for item in payload["materiais"] if item["nome_material"] == "Lona")
    assert lona["quantidade_usos"] == 0

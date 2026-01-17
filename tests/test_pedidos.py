""" 
Testes para endpoints de pedidos.
Cobre criação, listagem, atualização, deleção e filtros.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime
import pedidos.router
from pedidos.schema import Status, ItemPedido, Acabamento, PedidoImagem
from sqlalchemy import text
import asyncio

SAMPLE_IMAGE_DATA = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)

SAMPLE_IMAGE_DATA_ALT = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAE0lEQVR42mP8z/C/HwMDAwMjAAAzNQOijvOLLAAAAABJRU5ErkJggg=="
)


@pytest.mark.asyncio
async def test_criar_pedido_sucesso(client: AsyncClient, clean_db):
    """Testa criação de pedido com sucesso."""
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
    
    response = await client.post("/pedidos/", json=pedido_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verificar que o pedido foi criado
    assert data["id"] is not None
    assert data["cliente"] == "João Silva"
    assert len(data["items"]) == 1
    assert data["items"][0]["descricao"] == "Painel promocional"
    


@pytest.mark.asyncio
async def test_criar_pedido_incrementa_id(client: AsyncClient, clean_db):
    """Testa que cada novo pedido recebe um ID válido e diferente."""
    
    pedido_base = {
        "cliente": "Cliente Teste",
        "data_entrada": "2024-01-15",
        "items": []
    }
    
    # Criar primeiro pedido
    response1 = await client.post("/pedidos/", json=pedido_base)
    assert response1.status_code == 200
    id1 = response1.json()["id"]
    
    # Criar segundo pedido
    pedido_base["cliente"] = "Cliente Teste 2"
    response2 = await client.post("/pedidos/", json=pedido_base)
    assert response2.status_code == 200
    id2 = response2.json()["id"]
    
    # IDs devem ser diferentes e positivos
    assert id1 is not None and id1 > 0
    assert id2 is not None and id2 > 0
    assert id2 != id1


@pytest.mark.asyncio
async def test_criar_pedido_gera_numero_incremental_unico(client: AsyncClient, clean_db, test_session):
    """
    Garante que o campo numero é gerado incrementalmente e sem duplicidade.
    """
    # limpa tabela explicitamente
    await test_session.execute(text("DELETE FROM pedidos"))
    await test_session.commit()

    base = {
        "cliente": "Cliente Numeração",
        "data_entrada": "2024-01-15",
        "items": [],
    }

    resp1 = await client.post("/pedidos/", json=base)
    resp2 = await client.post("/pedidos/", json=base)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    num1 = resp1.json()["numero"]
    num2 = resp2.json()["numero"]

    assert num1 is not None
    assert num2 is not None
    assert num1 != num2
    # ambos com mesmo padding de 10 dígitos
    assert len(num1) == 10
    assert len(num2) == 10


@pytest.mark.asyncio
async def test_listar_pedidos(client: AsyncClient, clean_db):
    """Testa listagem de pedidos."""
    # Criar alguns pedidos
    for i in range(3):
        await client.post("/pedidos/", json={
            "cliente": f"Cliente {i}",
            "data_entrada": "2024-01-15",
            "items": []
        })
    
    response = await client.get("/pedidos/")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    assert all("id" in pedido for pedido in data)
    assert all("cliente" in pedido for pedido in data)


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_cliente(client: AsyncClient, clean_db):
    """Testa filtro por nome do cliente."""
    # Criar pedidos com clientes diferentes
    await client.post("/pedidos/", json={
        "cliente": "João Silva",
        "data_entrada": "2024-01-15",
        "items": []
    })
    await client.post("/pedidos/", json={
        "cliente": "Maria Santos",
        "data_entrada": "2024-01-15",
        "items": []
    })
    
    # Filtrar por "João"
    response = await client.get("/pedidos/?cliente=João")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert "João" in data[0]["cliente"]


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_data(client: AsyncClient, clean_db):
    """Testa filtro por data de entrada."""
    # Criar pedidos em datas diferentes
    await client.post("/pedidos/", json={
        "cliente": "Cliente 1",
        "data_entrada": "2024-01-15",
        "items": []
    })
    await client.post("/pedidos/", json={
        "cliente": "Cliente 2",
        "data_entrada": "2024-01-20",
        "items": []
    })
    
    # Filtrar por período
    response = await client.get("/pedidos/?data_inicio=2024-01-15&data_fim=2024-01-16")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["data_entrada"] == "2024-01-15"


@pytest.mark.asyncio
async def test_listar_pedidos_com_filtro_status(client: AsyncClient, clean_db):
    """Testa filtro por status."""
    # Criar pedidos com status diferentes
    await client.post("/pedidos/", json={
        "cliente": "Cliente 1",
        "data_entrada": "2024-01-15",
        "status": "pendente",
        "items": []
    })
    await client.post("/pedidos/", json={
        "cliente": "Cliente 2",
        "data_entrada": "2024-01-15",
        "status": "em_producao",
        "items": []
    })
    
    # Filtrar por status pendente
    response = await client.get("/pedidos/?status=pendente")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["status"] == "pendente"


@pytest.mark.asyncio
async def test_obter_pedido_por_id(client: AsyncClient, clean_db):
    """Testa obter pedido específico por ID."""
    # Criar pedido
    create_response = await client.post("/pedidos/", json={
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
    create_response = await client.post("/pedidos/", json={
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
async def test_deletar_pedido(client: AsyncClient, clean_db, admin_headers):
    """Testa deleção de pedido."""
    # Criar pedido
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente Para Deletar",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]
    
    # Deletar pedido
    response = await client.delete(f"/pedidos/{pedido_id}", headers=admin_headers)
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
    
    response = await client.post("/pedidos/", json=pedido_data)
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["acabamento"] is not None
    assert item["acabamento"]["overloque"] is True
    assert item["acabamento"]["ilhos"] is True


@pytest.mark.asyncio
async def test_nao_deleta_pedido_sem_autenticacao(client: AsyncClient, clean_db):
    """Garante que rotas protegidas exigem token."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente Restrito",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]

    response = await client.delete(f"/pedidos/{pedido_id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_financeiro_requer_admin(client: AsyncClient, clean_db):
    """Atualização do campo financeiro deve exigir admin."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente Financeiro",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]

    response = await client.patch(f"/pedidos/{pedido_id}", json={"financeiro": True})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_financeiro_com_admin(client: AsyncClient, clean_db, admin_headers):
    """Admins conseguem atualizar o campo financeiro."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente Financeiro Admin",
        "data_entrada": "2024-01-15",
        "items": []
    })
    pedido_id = create_response.json()["id"]

    response = await client.patch(
        f"/pedidos/{pedido_id}",
        json={"financeiro": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["financeiro"] is True


@pytest.mark.asyncio
async def test_criar_varios_pedidos_em_paralelo(client: AsyncClient, clean_db, test_session):
    """
    Cria vários pedidos em paralelo para simular concorrência básica.
    Deve retornar todos 200 e numeros únicos.
    """

    async def _criar(i: int):
        return await client.post(
            "/pedidos/",            json={
                "cliente": f"Cliente {i}",
                "data_entrada": "2024-01-15",
                "items": [],
            },
        )

    # 5 requisições em paralelo
    responses = await asyncio.gather(*[_criar(i) for i in range(5)])

    assert all(r.status_code == 200 for r in responses)

    numeros = [r.json()["numero"] for r in responses]
    # todos os números devem ser únicos
    assert len(numeros) == len(set(numeros))


@pytest.mark.asyncio
async def test_atualizar_pedido_numero_duplicado_retorna_409(client: AsyncClient, clean_db, test_session):
    """
    Atualizar numero para um valor já usado deve retornar 409 (conflito).
    """
    # criar dois pedidos
    base = {
        "cliente": "Cliente conflito",
        "data_entrada": "2024-01-15",
        "items": [],
    }
    r1 = await client.post("/pedidos/", json=base)
    r2 = await client.post("/pedidos/", json=base)
    assert r1.status_code == 200
    assert r2.status_code == 200

    p1 = r1.json()
    p2 = r2.json()

    # tentar forçar o segundo a ter o mesmo numero do primeiro
    resp_conflict = await client.patch(f"/pedidos/{p2['id']}", json={"numero": p1["numero"]})
    assert resp_conflict.status_code == 409


@pytest.mark.asyncio
async def test_criar_pedido_salva_imagem_e_expoe_download(client: AsyncClient, clean_db, media_root):
    """Cria pedido com imagem em base64 e verifica URL e arquivo salvo."""
    pedido_data = {
        "cliente": "Cliente com imagem",
        "data_entrada": "2024-01-15",
                    "items": [
                        {
                            #"id": "item-1",  # Removido ID inválido (string em campo int)
                            "descricao": "Banner com arte",
                            "tipo_producao": "banner",                "imagem": SAMPLE_IMAGE_DATA,
            }
        ]
    }

    response = await client.post("/pedidos/", json=pedido_data)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["imagem"].startswith("/pedidos/imagens/")

    # arquivo físico precisa existir no diretório temporário
    files = [p for p in (media_root / "pedidos").rglob("*") if p.is_file()]
    assert len(files) == 1

    # endpoint de download deve servir o conteúdo binário
    download = await client.get(item["imagem"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    assert download.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_criar_pedido_retorna_imagem_path(client: AsyncClient, clean_db, media_root):
    """Resposta deve incluir caminho físico relativo da imagem salva."""
    response = await client.post("/pedidos/", json={
        "cliente": "Cliente com caminho",
        "data_entrada": "2024-01-15",
                    "items": [
                        {
                            #"id": "legacy-item", # Removido ID inválido
                            "descricao": "Item com arte",
                            "tipo_producao": "banner",                "imagem": SAMPLE_IMAGE_DATA,
            }
        ]
    })
    assert response.status_code == 200
    item = response.json()["items"][0]

    assert item["imagem"].startswith("/pedidos/imagens/")
    assert item["imagem_path"].startswith("pedidos/")

    saved_file = media_root / item["imagem_path"]
    assert saved_file.exists()
    assert saved_file.is_file()


@pytest.mark.asyncio
async def test_respostas_populam_imagem_path_para_registros_antigos(
    client: AsyncClient,
    clean_db,
    test_session,
    media_root,
):
    """Itens sem imagem no JSON devem receber URL e caminho baseado em PedidoImagem existente."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente legado",
        "data_entrada": "2024-01-15",
        "items": [
            {
                "id": 123,
                "descricao": "Item legado",
                "tipo_producao": "banner",
            }
        ]
    })
    assert create_response.status_code == 200
    pedido_id = create_response.json()["id"]

    legacy_path = f"pedidos/{pedido_id}/legacy.png"
    legacy_file = media_root / legacy_path
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_bytes(b"\x89PNG")

    image_row = PedidoImagem(
        pedido_id=pedido_id,
        item_index=0,
        item_identificador="123",
        filename="legacy.png",
        mime_type="image/png",
        path=legacy_path,
        tamanho=4,
    )
    test_session.add(image_row)
    await test_session.commit()
    await test_session.refresh(image_row)

    list_response = await client.get("/pedidos/")
    assert list_response.status_code == 200
    pedido_data = list_response.json()[0]
    item = pedido_data["items"][0]

    assert item["imagem"].endswith(f"/{image_row.id}")
    assert item["imagem_path"] == legacy_path

    detail_response = await client.get(f"/pedidos/{pedido_id}")
    assert detail_response.status_code == 200
    detail_item = detail_response.json()["items"][0]
    assert detail_item["imagem_path"] == legacy_path
@pytest.mark.asyncio
async def test_atualizar_pedido_substitui_imagem_antiga(client: AsyncClient, clean_db, media_root):
    """Atualizar item com nova imagem troca o arquivo salvo e remove o antigo."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente troca imagem",
        "data_entrada": "2024-01-15",
        "items": [
            {
                "id": 111,
                "descricao": "Peça com imagem",
                "tipo_producao": "banner",
                "imagem": SAMPLE_IMAGE_DATA,
            }
        ]
    })
    assert create_response.status_code == 200
    pedido_id = create_response.json()["id"]
    item = create_response.json()["items"][0]
    imagem_antiga = item["imagem"]

    update_response = await client.patch(f"/pedidos/{pedido_id}", json={
        "items": [
            {
                "id": 111,
                "descricao": "Peça com imagem",
                "tipo_producao": "banner",
                "imagem": SAMPLE_IMAGE_DATA_ALT,
            }
        ]
    })
    assert update_response.status_code == 200
    nova_imagem = update_response.json()["items"][0]["imagem"]
    assert nova_imagem != imagem_antiga

    antigo = await client.get(imagem_antiga)
    assert antigo.status_code == 404
    novo = await client.get(nova_imagem)
    assert novo.status_code == 200

    files = [p for p in (media_root / "pedidos").rglob("*") if p.is_file()]
    assert len(files) == 1


@pytest.mark.asyncio
async def test_atualizar_pedido_remove_imagem_quando_nula(client: AsyncClient, clean_db, media_root):
    """Enviar imagem nula remove arquivo registrado e atualiza item."""
    create_response = await client.post("/pedidos/", json={
        "cliente": "Cliente remove imagem",
        "data_entrada": "2024-01-15",
                    "items": [
                        {
                            "id": 222,
                            "descricao": "Peça com imagem",
                            "tipo_producao": "banner",                "imagem": SAMPLE_IMAGE_DATA,
            }
        ]
    })
    assert create_response.status_code == 200
    pedido_id = create_response.json()["id"]
    imagem_antiga = create_response.json()["items"][0]["imagem"]

    update_response = await client.patch(f"/pedidos/{pedido_id}", json={
        "items": [
            {
                "id": 222,
                "descricao": "Peça com imagem",
                "tipo_producao": "banner",
                "imagem": None,
            }
        ]
    })
    assert update_response.status_code == 200
    assert update_response.json()["items"][0]["imagem"] is None

    antigo = await client.get(imagem_antiga)
    assert antigo.status_code == 404

    files = [p for p in (media_root / "pedidos").rglob("*") if p.is_file()]
    assert len(files) == 0
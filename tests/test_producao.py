from fastapi.testclient import TestClient
from main import app

def test_clientes():
    with TestClient(app) as client:
        response = client.get("/clientes/")
    assert response.status_code == 200


def test_pedidos():
    with TestClient(app) as client:
        response = client.get("/pedidos/")
    assert response.status_code == 200


def test_envios():
    with TestClient(app) as client:
        response = client.get("/tipos-envios/")
    assert response.status_code == 200


def test_pagamentos():
    with TestClient(app) as client:
        response = client.get("/tipos-pagamentos/")
    assert response.status_code == 200


# @pytest.mark.parametrize("i", range(30000))
# def test_create_300_clientes(i):
#     cliente_data = {
#         "nome": f"Cliente {i}",
#         "cep": f"00000-{1000 + i}",
#         "cidade": "Cidade Exemplo",
#         "estado": "EX",
#         "telefone": f"99999-99{i:02d}"
#     }
#     response = client.post("/clientes/", json=cliente_data)
#     assert response.status_code in (200, 201), f"Falha no cliente {i}"
#     data = response.json()
#     assert data["nome"] == cliente_data["nome"]
#     assert data["cep"] == cliente_data["cep"]
#     assert data["cidade"] == cliente_data["cidade"]
#     assert data["estado"] == cliente_data["estado"]
#     assert data["telefone"] == cliente_data["telefone"]

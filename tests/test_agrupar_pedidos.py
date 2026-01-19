import json

from pedidos.utils import agrupar_pedidos


def test_agrupar_pedidos_dedup_e_produtos() -> None:
    with open("tests/fixtures/controle_producao_dataset.json", "r", encoding="utf-8") as f:
        registros = json.load(f)

    pedidos = agrupar_pedidos(registros)

    assert len(pedidos) == 3

    pedido_115 = next(p for p in pedidos if p.get("numero") == "0000000115")
    pedido_116 = next(p for p in pedidos if p.get("numero") == "0000000116")
    pedido_117 = next(p for p in pedidos if p.get("numero") == "0000000117")

    assert len(pedido_115["produtos"]) == 2
    assert len(pedido_116["produtos"]) == 1
    assert len(pedido_117["produtos"]) == 1

    assert pedido_115.get("cliente") == "Cliente Alpha"
    assert pedido_116.get("forma_envio") == "Transportadora"

import pytest
import json
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from decimal import Decimal

from pedidos.schema import Pedido
from pedidos.pricing import normalize_order_financials
from pedidos.service import items_to_json_string

@pytest.mark.asyncio
async def test_legacy_recalc_logic(clean_db, test_session: AsyncSession):
    """
    Simula um pedido legado inconsistente no banco e valida que a rotina de
    reconciliação (que os scripts usam) corrige os dados corretamente.
    """
    # 1. Inserir pedido inconsistente manualmente (contornando o router)
    # Painel 100 + 18 ilhos = deveria ser 118, mas salvamos 100 nos itens e 118 no total
    legacy_items = [
        {
            "tipo_producao": "painel",
            "valor_painel": "100.00",
            "valor_unitario": "100.00", # INCONSISTENTE: falta ilhos
            "tipo_acabamento": "ilhos",
            "quantidade_ilhos": "18",
            "valor_ilhos": "1.00",
            "quantidade_paineis": "1",
        }
    ]
    
    pedido = Pedido(
        cliente="Legado Inconsistente",
        data_entrada="2023-01-01",
        valor_itens="100.00",
        valor_total="118.00", # Total até tava certo, mas itens errados
        valor_frete="0.00",
        items=json.dumps(legacy_items)
    )
    test_session.add(pedido)
    await test_session.commit()
    await test_session.refresh(pedido)
    pedido_id = pedido.id

    # 2. Executar Lógica de Reconciliação (mesma usada nos scripts)
    items_raw = json.loads(pedido.items)
    items_norm, totais = normalize_order_financials(items_raw, pedido.valor_frete)
    
    # Aplicar correção
    pedido.items = items_to_json_string(items_norm)
    pedido.valor_itens = totais["valor_itens"]
    pedido.valor_total = totais["valor_total"]
    
    test_session.add(pedido)
    await test_session.commit()
    await test_session.refresh(pedido)

    # 3. Assertions
    assert float(pedido.valor_total) == 118.00
    assert float(pedido.valor_itens) == 118.00 # Corrigido de 100 para 118
    
    items_corrigidos = json.loads(pedido.items)
    assert float(items_corrigidos[0]["valor_unitario"]) == 118.00

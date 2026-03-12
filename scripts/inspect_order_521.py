import asyncio
import json
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from pedidos.schema import Pedido
from pedidos.pricing import calculate_item_unit_price, _derive_item_qty, parse_money

async def inspect():
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Buscar o pedido 521
        result = await session.execute(select(Pedido).where(Pedido.id == 521))
        order = result.scalar_one_or_none()
        
        if not order:
            print("Pedido 521 não encontrado.")
            return

        print(f"--- Pedido {order.id} ---")
        print(f"Cliente: {order.cliente}")
        print(f"Valor Total (DB): {order.valor_total}")
        print(f"Valor Itens (DB): {order.valor_itens}")
        print(f"Valor Frete (DB): {order.valor_frete}")
        
        items = json.loads(order.items) if order.items else []
        print(f"\nItems ({len(items)}):")
        
        total_recalc = 0
        for i, item in enumerate(items):
            unit_db = item.get("valor_unitario")
            unit_recalc = calculate_item_unit_price(item)
            qty = _derive_item_qty(item)
            
            tipo = item.get("tipo_producao")
            v_painel = item.get("valor_painel")
            acab = item.get("tipo_acabamento")
            q_ilhos = item.get("quantidade_ilhos")
            v_ilhos = item.get("valor_ilhos")
            
            print(f"  Item {i}:")
            print(f"    Tipo: {tipo}")
            print(f"    Acabamento: {acab}")
            print(f"    Valor Painel: {v_painel}")
            print(f"    Ilhos: {q_ilhos} x {v_ilhos}")
            print(f"    Valor Unitário (DB): {unit_db}")
            print(f"    Valor Unitário (Recalc): {unit_recalc}")
            print(f"    Quantidade: {qty}")
            
            total_recalc += float(unit_recalc * qty)
            
        frete = float(parse_money(order.valor_frete))
        print(f"\nSoma Itens (Recalc): {total_recalc:.2f}")
        print(f"Valor Total (Recalc + Frete): {total_recalc + frete:.2f}")

if __name__ == "__main__":
    asyncio.run(inspect())

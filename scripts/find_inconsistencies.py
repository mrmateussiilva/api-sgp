import asyncio
import json
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

from config import settings
from pedidos.schema import Pedido
from pedidos.pricing import calculate_order_totals, parse_money, recalculate_items_totals

async def find_inconsistencies():
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    inconsistent_ids = []
    
    async with async_session() as session:
        result = await session.execute(select(Pedido))
        orders = result.scalars().all()
        
        print(f"Analisando {len(orders)} pedidos...")
        
        for order in orders:
            try:
                items = json.loads(order.items) if order.items else []
                # Usar a função de pricing para ver o que o backend calcula hoje
                # Note: normalize_order_financials retorna items_norm e totais
                items_norm = recalculate_items_totals(items)
                totais = calculate_order_totals(items_norm, order.valor_frete)
                
                esperado = parse_money(totais["valor_total"])
                real = parse_money(order.valor_total)
                
                if abs(esperado - real) > Decimal("0.02"):
                    inconsistent_ids.append(order.id)
                    print(f"Pedido {order.id} INCONSISTENTE: Banco {real} != Recalc {esperado}")
            except Exception as e:
                print(f"Erro ao analisar pedido {order.id}: {e}")
                
    print(f"\nTotal de pedidos inconsistentes encontrados: {len(inconsistent_ids)}")
    print(f"IDs: {inconsistent_ids}")

if __name__ == "__main__":
    asyncio.run(find_inconsistencies())

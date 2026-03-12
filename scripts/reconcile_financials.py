import asyncio
import json
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
import sys

from config import settings
from pedidos.schema import Pedido
from pedidos.pricing import normalize_order_financials
from pedidos.service import items_to_json_string

async def reconcile_all(dry_run: bool = True):
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(select(Pedido))
        orders = result.scalars().all()
        
        corrected_count = 0
        
        for order in orders:
            try:
                items = json.loads(order.items) if order.items else []
                
                # O Guardrail central que implementamos!
                # normalize_order_financials(items, valor_frete) -> (items_norm, totais)
                items_norm, totais = normalize_order_financials(items, order.valor_frete)
                
                new_valor_itens = totais["valor_itens"]
                new_valor_total = totais["valor_total"]
                new_items_json = json.dumps(items_norm) # Simplificado para o script
                
                # Comparar com o banco
                changed = (
                    new_valor_itens != order.valor_itens or
                    new_valor_total != order.valor_total or
                    new_items_json != order.items
                )
                
                if changed:
                    print(f"Pedido {order.id}: Corrigindo {order.valor_total} -> {new_valor_total}")
                    if not dry_run:
                        order.valor_itens = new_valor_itens
                        order.valor_total = new_valor_total
                        order.items = items_to_json_string(items_norm) # Usar helper do service se disponível
                        session.add(order)
                    corrected_count += 1
                    
            except Exception as e:
                print(f"Erro no pedido {order.id}: {e}")
        
        if not dry_run and corrected_count > 0:
            await session.commit()
            print(f"\nSucesso: {corrected_count} pedidos atualizados no banco.")
        else:
            print(f"\n[DRY RUN] {corrected_count} pedidos seriam corrigidos.")

if __name__ == "__main__":
    dry = "--commit" not in sys.argv
    asyncio.run(reconcile_all(dry_run=dry))

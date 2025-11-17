"""
Remove todos os pedidos da base.

Uso:
    python scripts/clear_pedidos.py
"""

import asyncio

from sqlmodel import delete

from database.database import async_session_maker
from pedidos.schema import Pedido


async def clear_orders() -> int:
    async with async_session_maker() as session:
        result = await session.execute(delete(Pedido))
        await session.commit()
        # rowcount pode ser None dependendo do driver; default para 0
        return result.rowcount or 0


async def main() -> None:
    deleted = await clear_orders()
    print(f"Pedidos removidos: {deleted}")


if __name__ == "__main__":
    asyncio.run(main())

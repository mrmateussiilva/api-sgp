import asyncio
import logging
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from database.database import engine
from pedidos.schema import Pedido
from pedidos.router import pedido_to_response_dict, json_string_to_items, populate_items_with_image_paths
from pedidos.schema import PedidoResponse
from shared.vps_sync_service import vps_sync_service

# Configurar logging para ver o progresso no terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bulk_sync")

async def sync_all():
    async with AsyncSession(engine) as session:
        # 1. Buscar todos os pedidos
        logger.info("Buscando todos os pedidos no banco de dados...")
        statement = select(Pedido)
        results = await session.exec(statement)
        pedidos = results.all()
        
        total = len(pedidos)
        logger.info(f"Encontrados {total} pedidos. Iniciando sincronização...")

        for i, pedido in enumerate(pedidos, 1):
            try:
                # 2. Preparar dados (mesma lógica do router)
                items = json_string_to_items(pedido.items or "[]")
                await populate_items_with_image_paths(session, pedido.id, items)
                
                pedido_dict = pedido_to_response_dict(pedido, items)
                response_obj = PedidoResponse(**pedido_dict)
                
                # 3. Sincronizar
                logger.info(f"[{i}/{total}] Sincronizando pedido {pedido.id} (Nº {pedido.numero})...")
                await vps_sync_service.sync_pedido(response_obj)
                
                # Pequeno atraso para não sobrecarregar a VPS
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Erro ao sincronizar pedido {pedido.id}: {e}")

        logger.info("Sincronização em massa concluída!")

if __name__ == "__main__":
    asyncio.run(sync_all())

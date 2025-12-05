"""
Script para deletar todos os pedidos do banco de dados.
ATENÇÃO: Esta ação é irreversível!
"""

import asyncio
import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import async_session_maker
from sqlmodel import select
from pedidos.schema import Pedido, PedidoImagem
from pedidos.images import delete_media_file


async def delete_all_pedidos():
    """Deleta todos os pedidos e suas imagens."""
    async with async_session_maker() as session:
        try:
            # Buscar todos os pedidos
            result = await session.exec(select(Pedido))
            all_pedidos = result.all()
            
            if not all_pedidos:
                print("✅ Nenhum pedido encontrado para deletar.")
                return
            
            print(f"📋 Encontrados {len(all_pedidos)} pedidos para deletar...")
            
            # Deletar imagens de todos os pedidos
            total_images = 0
            for pedido in all_pedidos:
                images_result = await session.exec(
                    select(PedidoImagem).where(PedidoImagem.pedido_id == pedido.id)
                )
                for image in images_result.all():
                    delete_media_file(image.path)
                    await session.delete(image)
                    total_images += 1
            
            if total_images > 0:
                print(f"🗑️  {total_images} imagens deletadas.")
            
            # Deletar todos os pedidos (os itens serão deletados em cascata)
            for pedido in all_pedidos:
                await session.delete(pedido)
            
            await session.commit()
            print(f"✅ {len(all_pedidos)} pedidos deletados com sucesso!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Erro ao deletar pedidos: {str(e)}")
            raise


if __name__ == "__main__":
    print("⚠️  ATENÇÃO: Esta ação irá deletar TODOS os pedidos do banco de dados!")
    print("⚠️  Esta ação é IRREVERSÍVEL!")
    resposta = input("Deseja continuar? (digite 'SIM' para confirmar): ")
    
    if resposta.strip().upper() == "SIM":
        asyncio.run(delete_all_pedidos())
    else:
        print("❌ Operação cancelada.")


#!/usr/bin/env python3
"""
Script para esvaziar todos os pedidos do banco de dados e limpar arquivos de mídia.
ATENÇÃO: Esta ação é irreversível!

Uso:
    python scripts/clear_all_pedidos.py [--confirm]
    python scripts/clear_all_pedidos.py --confirm  # Pula confirmação interativa
"""

import argparse
import asyncio
import sys
import shutil
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.database import async_session_maker
from sqlmodel import select, delete
from pedidos.schema import Pedido, PedidoImagem
from pedidos.images import delete_media_file, MEDIA_ROOT, PEDIDOS_MEDIA_ROOT


async def clear_all_pedidos(clean_media: bool = True):
    """Esvazia todos os pedidos do banco e opcionalmente limpa arquivos de mídia."""
    async with async_session_maker() as session:
        try:
            # Contar pedidos antes de deletar
            result = await session.exec(select(Pedido))
            all_pedidos = list(result.all())
            total_pedidos = len(all_pedidos)
            
            if total_pedidos == 0:
                print("✅ Nenhum pedido encontrado no banco de dados.")
            else:
                print(f"📋 Encontrados {total_pedidos} pedidos para deletar...")
                
                # Deletar imagens associadas aos pedidos (PedidoImagem)
                images_result = await session.exec(select(PedidoImagem))
                all_images = list(images_result.all())
                total_images = len(all_images)
                
                if total_images > 0:
                    print(f"🗑️  Deletando {total_images} registros de imagens...")
                    for image in all_images:
                        try:
                            await delete_media_file(image.path)
                        except Exception as e:
                            print(f"   ⚠️  Erro ao deletar arquivo {image.path}: {e}")
                        await session.delete(image)
                
                # Deletar todos os pedidos (os itens serão deletados em cascata)
                print(f"🗑️  Deletando {total_pedidos} pedidos...")
                await session.exec(delete(Pedido))
                
                await session.commit()
                print(f"✅ {total_pedidos} pedidos deletados do banco de dados!")
                if total_images > 0:
                    print(f"✅ {total_images} registros de imagens deletados!")
            
            # Limpar arquivos de mídia se solicitado
            if clean_media:
                print()
                print("🧹 Limpando arquivos de mídia...")
                
                # Limpar diretório tmp (imagens temporárias)
                tmp_dir = PEDIDOS_MEDIA_ROOT / "tmp"
                if tmp_dir.exists():
                    tmp_files = list(tmp_dir.glob("*"))
                    tmp_count = len([f for f in tmp_files if f.is_file()])
                    if tmp_count > 0:
                        print(f"   🗑️  Removendo {tmp_count} arquivo(s) de pedidos/tmp/...")
                        for file_path in tmp_files:
                            if file_path.is_file():
                                try:
                                    file_path.unlink()
                                except Exception as e:
                                    print(f"      ⚠️  Erro ao deletar {file_path.name}: {e}")
                        print(f"   ✅ Diretório tmp limpo!")
                    else:
                        print(f"   ✅ Diretório tmp já está vazio")
                
                # Limpar diretórios de pedidos individuais (pedidos/{id}/)
                pedidos_dir = PEDIDOS_MEDIA_ROOT
                if pedidos_dir.exists():
                    pedido_dirs = [d for d in pedidos_dir.iterdir() if d.is_dir() and d.name.isdigit()]
                    if pedido_dirs:
                        print(f"   🗑️  Removendo {len(pedido_dirs)} diretório(s) de pedidos...")
                        for pedido_dir in pedido_dirs:
                            try:
                                shutil.rmtree(pedido_dir)
                            except Exception as e:
                                print(f"      ⚠️  Erro ao deletar {pedido_dir.name}: {e}")
                        print(f"   ✅ Diretórios de pedidos limpos!")
                    else:
                        print(f"   ✅ Nenhum diretório de pedido encontrado")
            
            print()
            print("✅ Limpeza concluída com sucesso!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Erro ao esvaziar pedidos: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Esvazia todos os pedidos do banco de dados e limpa arquivos de mídia',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Com confirmação interativa
  python scripts/clear_all_pedidos.py
  
  # Sem confirmação (útil para scripts)
  python scripts/clear_all_pedidos.py --confirm
  
  # Limpar apenas banco, manter arquivos de mídia
  python scripts/clear_all_pedidos.py --confirm --keep-media
        """
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Pula confirmação interativa (útil para scripts)'
    )
    parser.add_argument(
        '--keep-media',
        action='store_true',
        help='Não deleta arquivos de mídia, apenas registros do banco'
    )
    
    args = parser.parse_args()
    
    # Confirmação
    if not args.confirm:
        print("⚠️  ATENÇÃO: Esta ação irá deletar TODOS os pedidos do banco de dados!")
        print("⚠️  Esta ação é IRREVERSÍVEL!")
        if not args.keep_media:
            print("⚠️  Também serão deletados todos os arquivos de mídia (imagens) dos pedidos!")
        print()
        resposta = input("Deseja continuar? (digite 'SIM' para confirmar): ")
        
        if resposta.strip().upper() != "SIM":
            print("❌ Operação cancelada.")
            return 1
    
    try:
        asyncio.run(clear_all_pedidos(clean_media=not args.keep_media))
        return 0
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário.")
        return 1
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        return 1


if __name__ == "__main__":
    exit(main())


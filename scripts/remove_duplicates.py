#!/usr/bin/env python3
"""
Script para identificar e remover duplicatas do banco de dados.

Este script identifica registros duplicados em todas as tabelas principais
e remove as duplicatas, mantendo apenas o registro mais antigo (menor ID).

Uso:
    python scripts/remove_duplicates.py [--dry-run] [--table TABELA] [--confirm]
    
    --dry-run: Apenas mostra as duplicatas sem remover
    --table: Processa apenas uma tabela específica
    --confirm: Confirma automaticamente a remoção (sem prompt interativo)
"""

import asyncio
import argparse
import sys
from typing import Dict, List, Tuple, Any
from collections import defaultdict

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Importar modelos
from database.database import engine, async_session_maker
from clientes.schema import Cliente
from vendedores.schema import Vendedor
from designers.schema import Designer
from materiais.schema import Material
from pagamentos.schema import Payments
from envios.schema import Envio
from pedidos.schema import Pedido
from auth.models import User


class DuplicateRemover:
    """Classe para identificar e remover duplicatas."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "found": 0,
            "removed": 0,
            "kept": 0
        })
    
    async def find_duplicate_clientes(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra clientes duplicados (mesmo nome + telefone)."""
        # Buscar todos os clientes
        result = await session.exec(select(Cliente))
        clientes = result.all()
        
        # Agrupar por nome + telefone
        groups = defaultdict(list)
        for cliente in clientes:
            key = (cliente.nome.lower().strip(), cliente.telefone.strip())
            groups[key].append(cliente)
        
        # Retornar grupos com mais de um registro
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                # Ordenar por ID (manter o menor)
                group.sort(key=lambda x: x.id or 0)
                ids = [c.id for c in group[1:]]  # Todos exceto o primeiro
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["clientes"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_vendedores(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra vendedores duplicados (mesmo nome)."""
        result = await session.exec(select(Vendedor))
        vendedores = result.all()
        
        groups = defaultdict(list)
        for vendedor in vendedores:
            key = vendedor.nome.lower().strip()
            groups[key].append(vendedor)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [v.id for v in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["vendedores"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_designers(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra designers duplicados (mesmo nome)."""
        result = await session.exec(select(Designer))
        designers = result.all()
        
        groups = defaultdict(list)
        for designer in designers:
            key = designer.nome.lower().strip()
            groups[key].append(designer)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [d.id for d in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["designers"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_materiais(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra materiais duplicados (mesmo nome)."""
        result = await session.exec(select(Material))
        materiais = result.all()
        
        groups = defaultdict(list)
        for material in materiais:
            key = material.nome.lower().strip()
            groups[key].append(material)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [m.id for m in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["materiais"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_pagamentos(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra tipos de pagamento duplicados (mesmo nome)."""
        result = await session.exec(select(Payments))
        pagamentos = result.all()
        
        groups = defaultdict(list)
        for pagamento in pagamentos:
            key = pagamento.nome.lower().strip()
            groups[key].append(pagamento)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [p.id for p in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["pagamentos"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_envios(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra tipos de envio duplicados (mesmo nome)."""
        result = await session.exec(select(Envio))
        envios = result.all()
        
        groups = defaultdict(list)
        for envio in envios:
            key = envio.nome.lower().strip()
            groups[key].append(envio)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [e.id for e in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["envios"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_pedidos(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra pedidos duplicados (mesmo numero)."""
        # Buscar todos os pedidos
        result = await session.exec(select(Pedido).where(Pedido.numero.isnot(None), Pedido.numero != ""))
        pedidos = result.all()
        
        # Agrupar por numero
        groups = defaultdict(list)
        for pedido in pedidos:
            if pedido.numero:
                key = pedido.numero.strip()
                groups[key].append(pedido)
        
        # Retornar grupos com mais de um registro
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                # Ordenar por ID (manter o menor)
                group.sort(key=lambda x: x.id or 0)
                ids = [p.id for p in group[1:]]  # Todos exceto o primeiro
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["pedidos"]["found"] += len(group) - 1
        
        return duplicates
    
    async def find_duplicate_users(self, session: AsyncSession) -> List[Tuple[int, ...]]:
        """Encontra usuários duplicados (mesmo username)."""
        result = await session.exec(select(User))
        users = result.all()
        
        groups = defaultdict(list)
        for user in users:
            key = user.username.lower().strip()
            groups[key].append(user)
        
        duplicates = []
        for group in groups.values():
            if len(group) > 1:
                group.sort(key=lambda x: x.id or 0)
                ids = [u.id for u in group[1:]]
                duplicates.append((group[0].id, tuple(ids)))
                self.stats["users"]["found"] += len(group) - 1
        
        return duplicates
    
    async def remove_duplicates(
        self, 
        session: AsyncSession,
        model_class: Any,
        duplicates: List[Tuple[int, ...]],
        table_name: str
    ) -> int:
        """Remove duplicatas de uma tabela."""
        if not duplicates:
            return 0
        
        removed = 0
        for keep_id, remove_ids in duplicates:
            for remove_id in remove_ids:
                try:
                    record = await session.get(model_class, remove_id)
                    if record:
                        await session.delete(record)
                        removed += 1
                        self.stats[table_name]["removed"] += 1
                except Exception as e:
                    print(f"  ⚠️  Erro ao remover {table_name} ID {remove_id}: {e}")
        
        if not self.dry_run and removed > 0:
            await session.commit()
            self.stats[table_name]["kept"] = len(duplicates)
        
        return removed
    
    async def process_table(
        self,
        session: AsyncSession,
        table_name: str,
        find_func,
        model_class: Any
    ):
        """Processa uma tabela específica."""
        print(f"\n📊 Processando tabela: {table_name}")
        print("-" * 60)
        
        try:
            duplicates = await find_func(session)
            
            if not duplicates:
                print(f"  ✅ Nenhuma duplicata encontrada em {table_name}")
                return
            
            print(f"  🔍 Encontradas {len(duplicates)} duplicatas:")
            total_to_remove = sum(len(ids) for _, ids in duplicates)
            print(f"  📝 Total de registros a remover: {total_to_remove}")
            
            # Mostrar algumas duplicatas
            for i, (keep_id, remove_ids) in enumerate(duplicates[:5]):
                print(f"    - Manter ID {keep_id}, remover IDs: {', '.join(map(str, remove_ids))}")
            if len(duplicates) > 5:
                print(f"    ... e mais {len(duplicates) - 5} duplicatas")
            
            if not self.dry_run:
                removed = await self.remove_duplicates(session, model_class, duplicates, table_name)
                print(f"  ✅ Removidos {removed} registros duplicados")
            else:
                print(f"  🔍 [DRY-RUN] Seriam removidos {total_to_remove} registros")
                
        except Exception as e:
            print(f"  ❌ Erro ao processar {table_name}: {e}")
            import traceback
            traceback.print_exc()
    
    async def run(self, table_filter: str = None):
        """Executa a remoção de duplicatas em todas as tabelas."""
        print("=" * 60)
        print("🔍 Verificação de Duplicatas no Banco de Dados")
        print("=" * 60)
        
        if self.dry_run:
            print("\n⚠️  MODO DRY-RUN: Nenhuma alteração será feita\n")
        
        # Mapeamento de tabelas
        tables = {
            "clientes": (
                self.find_duplicate_clientes,
                Cliente
            ),
            "vendedores": (
                self.find_duplicate_vendedores,
                Vendedor
            ),
            "designers": (
                self.find_duplicate_designers,
                Designer
            ),
            "materiais": (
                self.find_duplicate_materiais,
                Material
            ),
            "pagamentos": (
                self.find_duplicate_pagamentos,
                Payments
            ),
            "envios": (
                self.find_duplicate_envios,
                Envio
            ),
            "pedidos": (
                self.find_duplicate_pedidos,
                Pedido
            ),
            "users": (
                self.find_duplicate_users,
                User
            ),
        }
        
        async with async_session_maker() as session:
            if table_filter:
                if table_filter not in tables:
                    print(f"❌ Tabela '{table_filter}' não encontrada")
                    print(f"   Tabelas disponíveis: {', '.join(tables.keys())}")
                    return
                find_func, model_class = tables[table_filter]
                await self.process_table(session, table_filter, find_func, model_class)
            else:
                for table_name, (find_func, model_class) in tables.items():
                    await self.process_table(session, table_name, find_func, model_class)
        
        # Resumo final
        print("\n" + "=" * 60)
        print("📊 RESUMO")
        print("=" * 60)
        
        total_found = sum(s["found"] for s in self.stats.values())
        total_removed = sum(s["removed"] for s in self.stats.values())
        
        for table_name, stats in self.stats.items():
            if stats["found"] > 0:
                print(f"  {table_name}:")
                print(f"    - Encontradas: {stats['found']} duplicatas")
                if not self.dry_run:
                    print(f"    - Removidas: {stats['removed']}")
                    print(f"    - Mantidas: {stats['kept']}")
        
        print(f"\n  Total de duplicatas encontradas: {total_found}")
        if not self.dry_run:
            print(f"  Total de duplicatas removidas: {total_removed}")
        else:
            print(f"  [DRY-RUN] Total que seria removido: {total_found}")


async def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicatas do banco de dados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Verificar duplicatas sem remover (dry-run)
  python scripts/remove_duplicates.py --dry-run
  
  # Remover duplicatas de uma tabela específica
  python scripts/remove_duplicates.py --table clientes
  
  # Remover todas as duplicatas (com confirmação)
  python scripts/remove_duplicates.py --confirm
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra as duplicatas sem remover"
    )
    
    parser.add_argument(
        "--table",
        type=str,
        help="Processa apenas uma tabela específica",
        choices=["clientes", "vendedores", "designers", "materiais", "pagamentos", "envios", "pedidos", "users"]
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma automaticamente a remoção (sem prompt interativo)"
    )
    
    args = parser.parse_args()
    
    # Se não for dry-run e não tiver --confirm, pedir confirmação
    if not args.dry_run and not args.confirm:
        print("\n⚠️  ATENÇÃO: Este script irá REMOVER registros duplicados do banco de dados!")
        print("   Recomendado: Execute primeiro com --dry-run para ver o que será removido")
        response = input("\n   Deseja continuar? (sim/não): ").strip().lower()
        if response not in ["sim", "s", "yes", "y"]:
            print("   Operação cancelada.")
            return
    
    remover = DuplicateRemover(dry_run=args.dry_run)
    await remover.run(table_filter=args.table)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


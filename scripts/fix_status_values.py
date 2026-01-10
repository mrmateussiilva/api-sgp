#!/usr/bin/env python3
"""
Script para corrigir valores de status no banco de dados.
Normaliza todos os status para valores minúsculos conforme o schema.
"""
import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "banco.db"

# Mapeamento de status antigos para novos (minúsculos)
STATUS_MAP = {
    'Pendente': 'pendente',
    'PENDENTE': 'pendente',
    'Em Producao': 'em_producao',
    'EM_PRODUCAO': 'em_producao',
    'Em Producção': 'em_producao',  # Com acentuação
    'Pronto': 'pronto',
    'PRONTO': 'pronto',
    'Entregue': 'entregue',
    'ENTREGUE': 'entregue',
    'Concluido': 'entregue',  # "Concluido" deve ser mapeado para "entregue"
    'CONCLUIDO': 'entregue',
    'Cancelado': 'cancelado',
    'CANCELADO': 'cancelado',
}

def fix_status_values(dry_run=True):
    """Corrige valores de status no banco de dados."""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return
    
    print("=" * 80)
    print("🔧 CORREÇÃO DE VALORES DE STATUS")
    print("=" * 80)
    print(f"Modo: {'SIMULAÇÃO (dry-run)' if dry_run else 'EXECUÇÃO REAL'}\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Buscar todos os status únicos
        cursor.execute("SELECT DISTINCT status FROM pedidos WHERE status IS NOT NULL")
        status_values = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Status encontrados no banco: {status_values}\n")
        
        # Identificar quais precisam ser corrigidos
        correcoes = []
        for status_antigo in status_values:
            status_novo = STATUS_MAP.get(status_antigo)
            if status_novo and status_novo != status_antigo:
                # Contar quantos pedidos têm esse status
                cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = ?", (status_antigo,))
                count = cursor.fetchone()[0]
                
                correcoes.append({
                    'antigo': status_antigo,
                    'novo': status_novo,
                    'count': count
                })
            elif status_antigo not in STATUS_MAP.values():
                # Status desconhecido - manter mas avisar
                cursor.execute("SELECT COUNT(*) FROM pedidos WHERE status = ?", (status_antigo,))
                count = cursor.fetchone()[0]
                print(f"⚠️  Status desconhecido '{status_antigo}' encontrado em {count} pedido(s)")
                print(f"   Não será alterado. Verifique se é válido.\n")
        
        if not correcoes:
            print("✅ Todos os status já estão corretos!")
            return
        
        print(f"📋 Encontradas {len(correcoes)} correções necessárias:\n")
        print("-" * 80)
        
        total_corrigidos = 0
        for corr in correcoes:
            print(f"{corr['antigo']} → {corr['novo']} ({corr['count']} pedido(s))")
            
            if not dry_run:
                cursor.execute(
                    "UPDATE pedidos SET status = ? WHERE status = ?",
                    (corr['novo'], corr['antigo'])
                )
                total_corrigidos += corr['count']
                print(f"  ✅ {corr['count']} pedido(s) atualizado(s)!")
            else:
                print(f"  ⏸️  (simulação - {corr['count']} pedido(s) seriam atualizados)")
            print()
        
        if not dry_run:
            conn.commit()
            print(f"✅ Total: {total_corrigidos} pedido(s) corrigido(s) com sucesso!")
        else:
            print(f"⏸️  Modo simulação - nenhuma alteração foi feita")
            print("   Execute com --execute para aplicar as correções")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        if not dry_run:
            conn.rollback()
    finally:
        conn.close()

def main():
    dry_run = '--execute' not in sys.argv
    fix_status_values(dry_run=dry_run)

if __name__ == "__main__":
    main()


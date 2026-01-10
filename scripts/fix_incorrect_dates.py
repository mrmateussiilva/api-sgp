#!/usr/bin/env python3
"""
Script opcional para corrigir datas de entrega incorretas no banco de dados
baseado nos arquivos JSON originais.
"""
import json
import sqlite3
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEDIA_PEDIDOS = PROJECT_ROOT / "media" / "pedidos"
DB_PATH = PROJECT_ROOT / "db" / "banco.db"

def fix_incorrect_dates(dry_run=True):
    """Corrige datas de entrega incorretas baseado nos JSONs."""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return
    
    print("🔧 Script de correção de datas")
    print(f"Modo: {'SIMULAÇÃO (dry-run)' if dry_run else 'EXECUÇÃO REAL'}\n")
    
    # Buscar todos os pedidos dos JSONs
    pedidos_json = {}
    for pedido_dir in MEDIA_PEDIDOS.iterdir():
        if not pedido_dir.is_dir() or pedido_dir.name == "tmp":
            continue
        
        try:
            pedido_id = int(pedido_dir.name)
        except ValueError:
            continue
        
        json_files = list(pedido_dir.glob("pedido-*.json"))
        if not json_files:
            continue
        
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_json = json_files[0]
        
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                pedidos_json[pedido_id] = {
                    'id': data.get('id'),
                    'data_entrega': data.get('data_entrega')
                }
        except Exception:
            continue
    
    # Conectar ao banco
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Buscar pedidos com datas diferentes
        correcoes = []
        for pedido_id, pedido_json in pedidos_json.items():
            json_data = (pedido_json.get('data_entrega') or '')[:10]
            if not json_data:
                continue
            
            # Buscar data atual no banco
            cursor.execute(
                "SELECT id, data_entrega FROM pedidos WHERE id = ?",
                (pedido_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                continue
            
            db_id, db_data = row
            db_data_only = (db_data or '')[:10] if db_data else ''
            
            if json_data != db_data_only and json_data and db_data_only:
                correcoes.append({
                    'id': pedido_id,
                    'json': json_data,
                    'db': db_data_only
                })
        
        if not correcoes:
            print("✅ Nenhuma correção necessária!")
            return
        
        print(f"📋 Encontradas {len(correcoes)} datas que precisam ser corrigidas:\n")
        print("-" * 80)
        
        for corr in correcoes:
            print(f"ID {corr['id']}: {corr['db']} → {corr['json']}")
            
            if not dry_run:
                cursor.execute(
                    "UPDATE pedidos SET data_entrega = ? WHERE id = ?",
                    (corr['json'], corr['id'])
                )
                print(f"  ✅ Corrigido!")
            else:
                print(f"  ⏸️  (simulação - não foi alterado)")
        
        if not dry_run:
            conn.commit()
            print(f"\n✅ {len(correcoes)} datas corrigidas com sucesso!")
        else:
            print(f"\n⚠️  Modo simulação - nenhuma alteração foi feita")
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
    fix_incorrect_dates(dry_run=dry_run)

if __name__ == "__main__":
    main()


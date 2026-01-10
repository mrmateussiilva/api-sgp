#!/usr/bin/env python3
"""
Script para verificar se os pedidos dos arquivos JSON existem no banco de dados
e comparar as datas de entrega.
"""
import json
import sqlite3
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Caminhos
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEDIA_PEDIDOS = PROJECT_ROOT / "media" / "pedidos"
DB_PATH = PROJECT_ROOT / "db" / "banco.db"

def extract_pedidos_from_json():
    """Extrai informações dos pedidos dos arquivos JSON."""
    pedidos_json = {}
    
    print("📂 Lendo arquivos JSON em media/pedidos/...")
    
    if not MEDIA_PEDIDOS.exists():
        print(f"❌ Diretório não encontrado: {MEDIA_PEDIDOS}")
        return {}
    
    for pedido_dir in MEDIA_PEDIDOS.iterdir():
        if not pedido_dir.is_dir() or pedido_dir.name == "tmp":
            continue
            
        try:
            pedido_id = int(pedido_dir.name)
        except ValueError:
            continue
        
        # Pegar o arquivo JSON mais recente de cada pedido
        json_files = list(pedido_dir.glob("pedido-*.json"))
        if not json_files:
            continue
        
        # Ordenar por data de modificação (mais recente primeiro)
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_json = json_files[0]
        
        try:
            with open(latest_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                pedidos_json[pedido_id] = {
                    'id': data.get('id'),
                    'numero': data.get('numero'),
                    'cliente': data.get('cliente') or data.get('customer_name'),
                    'data_entrada': data.get('data_entrada'),
                    'data_entrega': data.get('data_entrega'),
                    'status': data.get('status'),
                    'arquivo': latest_json.name
                }
        except Exception as e:
            print(f"⚠️ Erro ao ler {latest_json}: {e}")
    
    print(f"✅ Encontrados {len(pedidos_json)} pedidos nos arquivos JSON\n")
    return pedidos_json

def check_database_pedidos():
    """Verifica pedidos no banco de dados."""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Verificar se tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedidos'")
        if not cursor.fetchone():
            print("❌ Tabela 'pedidos' não existe no banco!")
            return None
        
        # Buscar todos os pedidos
        cursor.execute("""
            SELECT 
                id,
                numero,
                cliente,
                data_entrada,
                data_entrega,
                status
            FROM pedidos
            ORDER BY id
        """)
        
        pedidos_db = {}
        for row in cursor.fetchall():
            pedido_id, numero, cliente, data_entrada, data_entrega, status = row
            pedidos_db[pedido_id] = {
                'id': pedido_id,
                'numero': numero,
                'cliente': cliente,
                'data_entrada': data_entrada,
                'data_entrega': data_entrega,
                'status': status
            }
        
        print(f"✅ Encontrados {len(pedidos_db)} pedidos no banco de dados\n")
        return pedidos_db
        
    except Exception as e:
        print(f"❌ Erro ao consultar banco: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()

def compare_and_report(pedidos_json, pedidos_db):
    """Compara JSONs com banco e gera relatório."""
    if not pedidos_db:
        print("❌ Não foi possível verificar o banco de dados")
        return
    
    # Pedidos que estão nos JSONs
    ids_json = set(pedidos_json.keys())
    ids_db = set(pedidos_db.keys())
    
    # Estatísticas
    apenas_json = ids_json - ids_db
    apenas_db = ids_db - ids_json
    em_ambos = ids_json & ids_db
    
    print("=" * 80)
    print("📊 RELATÓRIO DE COMPARAÇÃO")
    print("=" * 80)
    print(f"\n✅ Pedidos em ambos (JSON + BD): {len(em_ambos)}")
    print(f"⚠️ Pedidos apenas nos JSONs: {len(apenas_json)}")
    print(f"⚠️ Pedidos apenas no BD: {len(apenas_db)}")
    
    # Analisar datas de entrega
    print("\n" + "=" * 80)
    print("📅 ANÁLISE DE DATAS DE ENTREGA")
    print("=" * 80)
    
    # Agrupar por data de entrega (do JSON)
    por_data = defaultdict(list)
    for pedido_id in em_ambos:
        pedido_json = pedidos_json[pedido_id]
        data_entrega = pedido_json.get('data_entrega')
        if data_entrega:
            # Extrair apenas YYYY-MM-DD se houver hora
            data_only = data_entrega[:10] if len(data_entrega) >= 10 else data_entrega
            por_data[data_only].append(pedido_id)
    
    # Mostrar distribuição por data
    print("\n📅 Distribuição de pedidos por data_entrega (dos JSONs):")
    print("-" * 80)
    for data in sorted(por_data.keys()):
        quantidade = len(por_data[data])
        print(f"  {data}: {quantidade} pedido(s)")
    
    # Verificar especificamente o dia 06
    dia_06_ids = por_data.get('2026-01-06', []) + por_data.get('2025-01-06', [])
    print(f"\n🔍 Pedidos do dia 06 encontrados nos JSONs: {len(dia_06_ids)}")
    
    if dia_06_ids:
        print("\n📋 Detalhes dos pedidos do dia 06:")
        print("-" * 80)
        for pedido_id in sorted(dia_06_ids):
            pedido_json = pedidos_json[pedido_id]
            pedido_db = pedidos_db.get(pedido_id)
            
            print(f"\n  Pedido ID: {pedido_id} - {pedido_json.get('numero', 'N/A')}")
            print(f"    Cliente: {pedido_json.get('cliente', 'N/A')}")
            print(f"    JSON - data_entrega: {pedido_json.get('data_entrega', 'N/A')}")
            
            if pedido_db:
                print(f"    BD - data_entrega: {pedido_db.get('data_entrega', 'N/A')}")
                
                # Verificar se as datas coincidem
                json_data = (pedido_json.get('data_entrega') or '')[:10]
                db_data = (pedido_db.get('data_entrega') or '')[:10] if pedido_db.get('data_entrega') else ''
                
                if json_data == db_data:
                    print(f"    ✅ Datas coincidem")
                else:
                    print(f"    ⚠️ DATAS DIFERENTES!")
                    
                # Verificar se aparece na query do banco
                print(f"    BD - data_entrada: {pedido_db.get('data_entrada', 'N/A')}")
            else:
                print(f"    ❌ Pedido não encontrado no banco!")
    
    # Verificar discrepâncias
    print("\n" + "=" * 80)
    print("⚠️ DISCREPÂNCIAS ENCONTRADAS")
    print("=" * 80)
    
    if apenas_json:
        print(f"\n❌ Pedidos apenas nos JSONs (não estão no BD): {sorted(apenas_json)}")
        print("   Esses pedidos podem ter sido perdidos na migração!")
        print("   Primeiros 10 pedidos ausentes:")
        for pedido_id in sorted(list(apenas_json))[:10]:
            pedido = pedidos_json[pedido_id]
            print(f"     - ID {pedido_id}: {pedido.get('numero')} - {pedido.get('cliente')} - data_entrega: {pedido.get('data_entrega')}")
    
    if apenas_db:
        print(f"\n⚠️ Pedidos apenas no BD (não têm JSON): {len(apenas_db)} pedidos")
        print("   Primeiros 10 pedidos sem JSON:")
        for pedido_id in sorted(list(apenas_db))[:10]:
            pedido = pedidos_db[pedido_id]
            print(f"     - ID {pedido_id}: {pedido.get('numero')} - {pedido.get('cliente')} - data_entrega: {pedido.get('data_entrega')}")
    
    # Verificar diferenças de data_entrega
    diferencas_data = []
    for pedido_id in em_ambos:
        pedido_json = pedidos_json[pedido_id]
        pedido_db = pedidos_db[pedido_id]
        
        json_data = (pedido_json.get('data_entrega') or '')[:10]
        db_data = (pedido_db.get('data_entrega') or '')[:10]
        
        if json_data and db_data and json_data != db_data:
            diferencas_data.append({
                'id': pedido_id,
                'numero': pedido_json.get('numero'),
                'json': json_data,
                'db': db_data
            })
    
    if diferencas_data:
        print(f"\n⚠️ Pedidos com data_entrega diferente entre JSON e BD ({len(diferencas_data)} pedidos):")
        for diff in diferencas_data[:10]:  # Mostrar apenas os 10 primeiros
            print(f"  ID {diff['id']} ({diff['numero']}): JSON={diff['json']}, BD={diff['db']}")
    else:
        print(f"\n✅ Todas as datas de entrega coincidem entre JSON e BD!")
    
    # Verificar pedidos do dia 06 no banco diretamente
    print("\n" + "=" * 80)
    print("🔍 VERIFICAÇÃO DIRETA NO BANCO DE DADOS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Buscar pedidos do dia 06 diretamente no banco
        cursor.execute("""
            SELECT 
                id, 
                numero, 
                cliente, 
                data_entrada,
                data_entrega,
                SUBSTR(data_entrega, 1, 10) as data_entrega_date
            FROM pedidos
            WHERE data_entrega IS NOT NULL
              AND (SUBSTR(data_entrega, 1, 10) = '2026-01-06' 
                   OR SUBSTR(data_entrega, 1, 10) = '2025-01-06'
                   OR data_entrega LIKE '2026-01-06%'
                   OR data_entrega LIKE '2025-01-06%')
            ORDER BY id
        """)
        
        pedidos_dia_06_bd = cursor.fetchall()
        
        print(f"\n📊 Pedidos do dia 06 encontrados diretamente no BD: {len(pedidos_dia_06_bd)}")
        
        if pedidos_dia_06_bd:
            print("\n📋 Lista de pedidos do dia 06 no banco:")
            print("-" * 80)
            for row in pedidos_dia_06_bd:
                pedido_id, numero, cliente, data_entrada, data_entrega, data_entrega_date = row
                print(f"  ID {pedido_id}: {numero} - {cliente}")
                print(f"    data_entrada: {data_entrada}")
                print(f"    data_entrega: {data_entrega}")
                print(f"    data_entrega (extraída): {data_entrega_date}")
        else:
            print("\n⚠️ NENHUM pedido do dia 06 encontrado no banco!")
            print("   Isso pode indicar que:")
            print("   1. Os pedidos do dia 06 não foram salvos no banco")
            print("   2. As datas estão em formato diferente no banco")
            print("   3. Os pedidos foram deletados ou perdidos na migração")
        
    except Exception as e:
        print(f"❌ Erro ao verificar pedidos do dia 06 no banco: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
    
    print("\n" + "=" * 80)
    print("✅ DIAGNÓSTICO CONCLUÍDO")
    print("=" * 80)
    
    # Resumo final
    print("\n📝 RESUMO FINAL:")
    print("-" * 80)
    print(f"✅ Pedidos em ambos: {len(em_ambos)}")
    if apenas_json:
        print(f"❌ Pedidos perdidos (apenas JSON): {len(apenas_json)}")
    if apenas_db:
        print(f"⚠️ Pedidos sem JSON: {len(apenas_db)}")
    print(f"📅 Pedidos do dia 06 nos JSONs: {len(dia_06_ids)}")
    
    # Verificar se os pedidos do dia 06 estão no banco
    pedidos_dia_06_no_bd = [pid for pid in dia_06_ids if pid in pedidos_db]
    print(f"📅 Pedidos do dia 06 no BD: {len(pedidos_dia_06_no_bd)}")
    
    if len(dia_06_ids) > 0 and len(pedidos_dia_06_no_bd) == 0:
        print("\n⚠️ ATENÇÃO: Há pedidos do dia 06 nos JSONs, mas NENHUM no banco!")
        print("   Isso indica perda de dados na migração ou problema de salvamento.")

def main():
    print("🔍 Iniciando diagnóstico de dados...\n")
    print(f"📁 Diretório JSONs: {MEDIA_PEDIDOS}")
    print(f"💾 Banco de dados: {DB_PATH}\n")
    
    # Extrair pedidos dos JSONs
    pedidos_json = extract_pedidos_from_json()
    
    if not pedidos_json:
        print("❌ Nenhum pedido encontrado nos arquivos JSON!")
        sys.exit(1)
    
    # Verificar banco de dados
    pedidos_db = check_database_pedidos()
    
    if not pedidos_db:
        print("❌ Não foi possível verificar o banco de dados!")
        sys.exit(1)
    
    # Comparar e gerar relatório
    compare_and_report(pedidos_json, pedidos_db)

if __name__ == "__main__":
    main()


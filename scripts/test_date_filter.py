#!/usr/bin/env python3
"""
Script de teste para verificar se o filtro de data está funcionando corretamente.
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "banco.db"

def test_date_filter():
    """Testa o filtro de data diretamente no banco."""
    if not DB_PATH.exists():
        print(f"❌ Banco não encontrado: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("🔍 Testando filtro de data do dia 06...\n")
        
        # Teste 1: Usando SUBSTR como no código corrigido
        print("Teste 1: Query usando SUBSTR (como no código corrigido):")
        cursor.execute("""
            SELECT 
                id, 
                numero, 
                cliente, 
                data_entrega,
                SUBSTR(data_entrega, 1, 10) as data_entrega_date
            FROM pedidos
            WHERE data_entrega IS NOT NULL
              AND SUBSTR(data_entrega, 1, 10) >= '2026-01-06'
              AND SUBSTR(data_entrega, 1, 10) <= '2026-01-06'
            ORDER BY id
        """)
        
        resultados = cursor.fetchall()
        print(f"✅ Encontrados {len(resultados)} pedidos do dia 06 usando SUBSTR")
        
        if resultados:
            print("\n📋 Pedidos encontrados:")
            for row in resultados[:10]:  # Mostrar apenas 10 primeiros
                pedido_id, numero, cliente, data_entrega, data_date = row
                print(f"  ID {pedido_id}: {numero} - {cliente} - data: {data_entrega}")
        
        # Teste 2: Comparação direta de strings
        print("\n" + "="*80)
        print("Teste 2: Query usando comparação direta (alternativa):")
        cursor.execute("""
            SELECT 
                id, 
                numero, 
                cliente, 
                data_entrega
            FROM pedidos
            WHERE data_entrega IS NOT NULL
              AND data_entrega >= '2026-01-06'
              AND data_entrega < '2026-01-07'
            ORDER BY id
        """)
        
        resultados2 = cursor.fetchall()
        print(f"✅ Encontrados {len(resultados2)} pedidos do dia 06 usando comparação direta")
        
        if resultados2:
            print("\n📋 Pedidos encontrados:")
            for row in resultados2[:10]:
                pedido_id, numero, cliente, data_entrega = row
                print(f"  ID {pedido_id}: {numero} - {cliente} - data: {data_entrega}")
        
        # Comparar resultados
        print("\n" + "="*80)
        ids_substr = {r[0] for r in resultados}
        ids_direto = {r[0] for r in resultados2}
        
        print(f"📊 Comparação:")
        print(f"  SUBSTR encontrou: {len(ids_substr)} pedidos")
        print(f"  Comparação direta encontrou: {len(ids_direto)} pedidos")
        
        apenas_substr = ids_substr - ids_direto
        apenas_direto = ids_direto - ids_substr
        
        if apenas_substr:
            print(f"  ⚠️ Pedidos apenas no SUBSTR: {sorted(apenas_substr)}")
        if apenas_direto:
            print(f"  ⚠️ Pedidos apenas na comparação direta: {sorted(apenas_direto)}")
        
        if ids_substr == ids_direto:
            print(f"  ✅ Ambos os métodos encontraram os mesmos pedidos!")
        
        # Teste 3: Buscar intervalo de datas (01 a 06)
        print("\n" + "="*80)
        print("Teste 3: Buscando pedidos de 01/01 a 06/01/2026:")
        cursor.execute("""
            SELECT 
                SUBSTR(data_entrega, 1, 10) as data,
                COUNT(*) as quantidade
            FROM pedidos
            WHERE data_entrega IS NOT NULL
              AND SUBSTR(data_entrega, 1, 10) >= '2026-01-01'
              AND SUBSTR(data_entrega, 1, 10) <= '2026-01-06'
            GROUP BY SUBSTR(data_entrega, 1, 10)
            ORDER BY data
        """)
        
        resultados3 = cursor.fetchall()
        print(f"\n📅 Distribuição de pedidos no intervalo:")
        for data, quantidade in resultados3:
            print(f"  {data}: {quantidade} pedido(s)")
        
        total = sum(qtd for _, qtd in resultados3)
        print(f"\n  Total no intervalo: {total} pedidos")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    test_date_filter()


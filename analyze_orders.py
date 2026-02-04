import sqlite3
import json
import decimal

def parse_decimal(value):
    if value is None:
        return decimal.Decimal(0)
    if isinstance(value, (int, float)):
        return decimal.Decimal(str(value))
    try:
        # Remove R$, dots and replace comma with dot
        clean = str(value).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return decimal.Decimal(clean)
    except:
        return decimal.Decimal(0)

def analyze():
    # Attempting to find the database
    db_paths = [
        "/home/mateus/Projetcs/api-sgp/db/dev.db",
        "/home/mateus/Projetcs/api-sgp/shared/db/banco.db",
        "/home/mateus/Projetcs/api-sgp/db/banco.db"
    ]
    
    conn = None
    for path in db_paths:
        try:
            conn = sqlite3.connect(path)
            # Check if 'pedidos' table exists
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedidos'")
            if cursor.fetchone():
                print(f"Connected to database: {path}")
                break
            conn.close()
            conn = None
        except:
            continue

    if not conn:
        print("Could not connect to database")
        return

    cursor = conn.cursor()
    
    # Range: January 2026
    start_date = "2026-01-01"
    end_date = "2026-01-31"
    
    # Query orders where data_entrada is in January
    cursor.execute("""
        SELECT id, numero, status, data_entrada, data_entrega, valor_total, valor_frete, items 
        FROM pedidos 
        WHERE date(data_entrada) BETWEEN ? AND ?
    """, (start_date, end_date))
    
    orders = cursor.fetchall()
    print(f"Found {len(orders)} orders in January (by data_entrada)")
    
    total_dashboard = decimal.Decimal(0)
    total_concluido = decimal.Decimal(0)
    total_recalculated_all = decimal.Decimal(0)
    total_recalculated_concluido = decimal.Decimal(0)
    
    status_counts = {}
    
    for row in orders:
        oid, numero, status, d_entrada, d_entrega, v_total, v_frete, items_json = row
        
        status_counts[status] = status_counts.get(status, 0) + 1
        
        v_total_dec = parse_decimal(v_total)
        v_frete_dec = parse_decimal(v_frete)
        
        total_dashboard += v_total_dec
        if status == 'CONCLUIDO' or status == 'PRONTO' or status == 'ENTREGUE':
            total_concluido += v_total_dec
            
        # Recalculate from items
        items = []
        try:
            items = json.loads(items_json or "[]")
        except:
            pass
            
        soma_itens = decimal.Decimal(0)
        for item in items:
            # Simple item subtotal calculation matching frontend logic
            subtotal = parse_decimal(item.get('subtotal', 0))
            if subtotal == 0:
                # Fallback to quantity * unit_price
                qty = item.get('quantity') or item.get('quantidade') or 1
                price = parse_decimal(item.get('unit_price') or item.get('valor_unitario') or 0)
                subtotal = decimal.Decimal(str(qty)) * price
            soma_itens += subtotal
            
        # Recalculated total for this order
        # Fechamento logic: sum(items) + frete - desconto
        # Discount is inferred if total_value < items + frete
        total_items_frete = soma_itens + v_frete_dec
        inferred_discount = max(decimal.Decimal(0), total_items_frete - v_total_dec)
        
        # In Fechamento, valor_liquido = total_items_frete - inferred_discount
        # Which should be EQUAL to v_total_dec if v_total_dec is not higher than total_items_frete.
        # But if total_items_frete < v_total_dec, then discount=0 and valor_liquido = total_items_frete.
        
        valor_liquido = total_items_frete - inferred_discount
        
        total_recalculated_all += valor_liquido
        if status == 'CONCLUIDO' or status == 'PRONTO' or status == 'ENTREGUE':
            total_recalculated_concluido += valor_liquido

    print("\n--- Statistics ---")
    print(f"Status distribution: {status_counts}")
    print(f"Total Dashboard (v_total sum): R$ {total_dashboard:,.2f}")
    print(f"Total Recalculated (All statuses): R$ {total_recalculated_all:,.2f}")
    print(f"Total Recalculated (Concluidos only): R$ {total_recalculated_concluido:,.2f}")
    
    print("\n--- Comparison ---")
    print(f"Difference Dashboard vs Recalculated All: R$ {total_dashboard - total_recalculated_all:,.2f}")
    print(f"Difference Dashboard vs Recalculated Concluido: R$ {total_dashboard - total_recalculated_concluido:,.2f}")

    conn.close()

if __name__ == "__main__":
    analyze()

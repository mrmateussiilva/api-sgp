#!/usr/bin/env python3
"""
Script de diagnóstico para verificar valores dos pedidos de uma data específica.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

# Função normalize_float_value standalone
def normalize_float_value(value):
    """Normaliza valores de string para float."""
    if value is None or value == '':
        return 0.0
    
    value_str = str(value).strip()
    
    if not value_str or value_str == 'None':
        return 0.0
    
    # Detecta formato e converte corretamente
    if ',' in value_str and '.' in value_str:
        # Verificar ordem: se vírgula vem depois do ponto, é formato brasileiro
        pos_virgula = value_str.rfind(',')
        pos_ponto = value_str.rfind('.')
        if pos_ponto > pos_virgula:
            # Formato misto: 1,955.00
            value_str = value_str.replace(',', '')
        else:
            # Formato brasileiro: 1.955,00
            value_str = value_str.replace('.', '').replace(',', '.')
    elif ',' in value_str:
        # Formato brasileiro: 1.955,00 ou 1955,00
        value_str = value_str.replace('.', '').replace(',', '.')
    elif '.' in value_str:
        # Formato americano: pode ser 1955.00 ou 1.955.00
        parts = value_str.split('.')
        if len(parts) > 2:
            decimal_part = parts[-1]
            integer_part = ''.join(parts[:-1])
            value_str = f"{integer_part}.{decimal_part}"
        elif len(parts) == 2:
            if len(parts[1]) <= 3:
                pass  # É decimal, mantém
            else:
                value_str = value_str.replace('.', '')
    
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return 0.0


def get_db_path():
    """Retorna o caminho do banco de dados."""
    # Tentar shared/db primeiro
    shared_db = Path(__file__).parent.parent / "shared" / "db" / "banco.db"
    if shared_db.exists():
        return shared_db
    
    # Fallback para db/banco.db
    db_path = Path(__file__).parent.parent / "db" / "banco.db"
    if db_path.exists():
        return db_path
    
    raise FileNotFoundError(f"Banco de dados não encontrado")


def diagnosticar_data(data: str):
    """Diagnostica os valores dos pedidos de uma data específica."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    
    print(f"\n{'='*60}")
    print(f"DIAGNOSTICO DE VALORES - Data: {data}")
    print(f"{'='*60}\n")
    
    # Primeiro, verificar quais datas existem
    cursor_check = conn.execute("SELECT DISTINCT data_entrada FROM pedidos ORDER BY data_entrada DESC LIMIT 10")
    datas_existentes = [row[0] for row in cursor_check.fetchall()]
    print(f"Ultimas 10 datas no banco: {datas_existentes}\n")
    
    # Buscar pedidos da data (tentar com e sem timestamp)
    query = """
        SELECT 
            id, numero, data_entrada, cliente,
            valor_total, valor_frete, valor_itens
        FROM pedidos
        WHERE data_entrada LIKE ?
        ORDER BY id
    """
    
    cursor = conn.execute(query, (f"{data}%",))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[ERRO] Nenhum pedido encontrado para a data {data}")
        conn.close()
        return
    
    print(f"Total de pedidos encontrados: {len(rows)}\n")
    
    # Calcular totais
    total_soma_valor_total = 0.0
    total_soma_frete = 0.0
    total_soma_itens = 0.0
    
    print(f"{'ID':<6} {'Número':<12} {'Cliente':<30} {'Valor Total':<15} {'Frete':<12} {'Itens':<12} {'Total Normalizado':<18}")
    print("-" * 110)
    
    for row in rows:
        pedido_id, numero, data_entrada, cliente, valor_total, valor_frete, valor_itens = row
        
        # Normalizar valores
        total_norm = normalize_float_value(valor_total)
        frete_norm = normalize_float_value(valor_frete)
        itens_norm = normalize_float_value(valor_itens)
        
        # Somas
        total_soma_valor_total += total_norm
        total_soma_frete += frete_norm
        total_soma_itens += itens_norm
        
        # Truncar cliente se muito longo
        cliente_display = cliente[:28] + ".." if len(cliente) > 30 else cliente
        
        print(f"{pedido_id:<6} {numero or 'N/A':<12} {cliente_display:<30} "
              f"{valor_total or '0.00':<15} {valor_frete or '0.00':<12} "
              f"{valor_itens or '0.00':<12} {total_norm:<18.2f}")
    
    print("-" * 110)
    print(f"\n{'RESUMO':<30} {'Valor Bruto':<20} {'Valor Normalizado':<20}")
    print("-" * 70)
    print(f"{'Soma valor_total':<30} {'':<20} {total_soma_valor_total:<20.2f}")
    print(f"{'Soma valor_frete':<30} {'':<20} {total_soma_frete:<20.2f}")
    print(f"{'Soma valor_itens':<30} {'':<20} {total_soma_itens:<20.2f}")
    print(f"{'Total (frete + itens)':<30} {'':<20} {total_soma_frete + total_soma_itens:<20.2f}")
    print(f"{'Diferença':<30} {'':<20} {total_soma_valor_total - (total_soma_frete + total_soma_itens):<20.2f}")
    
    # Verificar duplicatas
    print(f"\n{'='*60}")
    print("VERIFICAÇÃO DE DUPLICATAS")
    print(f"{'='*60}\n")
    
    # Verificar IDs duplicados
    ids = [row[0] for row in rows]
    ids_unicos = set(ids)
    if len(ids) != len(ids_unicos):
        print(f"[ATENCAO] Ha IDs duplicados!")
        from collections import Counter
        duplicados = [id for id, count in Counter(ids).items() if count > 1]
        print(f"   IDs duplicados: {duplicados}")
    else:
        print("[OK] Nenhum ID duplicado encontrado")
    
    # Verificar números duplicados
    numeros = [row[1] for row in rows if row[1]]
    numeros_unicos = set(numeros)
    if len(numeros) != len(numeros_unicos):
        print(f"[ATENCAO] Ha numeros de pedido duplicados!")
        from collections import Counter
        duplicados = [num for num, count in Counter(numeros).items() if count > 1]
        print(f"   Números duplicados: {duplicados}")
    else:
        print("[OK] Nenhum numero de pedido duplicado encontrado")
    
    # Verificar valores problemáticos
    print(f"\n{'='*60}")
    print("VALORES PROBLEMÁTICOS")
    print(f"{'='*60}\n")
    
    problemas = []
    for row in rows:
        pedido_id, numero, data_entrada, cliente, valor_total, valor_frete, valor_itens = row
        total_norm = normalize_float_value(valor_total)
        frete_norm = normalize_float_value(valor_frete)
        itens_norm = normalize_float_value(valor_itens)
        
        # Verificar se valor_total está muito diferente de frete + itens
        if valor_total and valor_frete and valor_itens:
            total_calculado = frete_norm + itens_norm
            diferenca = abs(total_norm - total_calculado)
            if diferenca > 0.01:  # Diferença maior que 1 centavo
                problemas.append({
                    'id': pedido_id,
                    'numero': numero,
                    'valor_total': total_norm,
                    'frete': frete_norm,
                    'itens': itens_norm,
                    'calculado': total_calculado,
                    'diferenca': diferenca
                })
    
    if problemas:
        print(f"[ATENCAO] Encontrados {len(problemas)} pedidos com valores inconsistentes:\n")
        for p in problemas:
            print(f"   Pedido {p['id']} ({p['numero']}):")
            print(f"      valor_total: {p['valor_total']:.2f}")
            print(f"      frete + itens: {p['calculado']:.2f}")
            print(f"      diferença: {p['diferenca']:.2f}\n")
    else:
        print("[OK] Nenhum valor problematico encontrado")
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"RESULTADO FINAL:")
    print(f"  Soma dos valor_total normalizados = R$ {total_soma_valor_total:.2f}")
    print(f"  Soma dos (frete + itens) = R$ {total_soma_frete + total_soma_itens:.2f}")
    print(f"  Se usar apenas pedidos com valor_total = frete + itens: ", end="")
    
    # Calcular apenas pedidos onde valor_total = frete + itens (dentro de 0.01 de tolerância)
    soma_consistente = 0.0
    for row in rows:
        pedido_id, numero, data_entrada, cliente, valor_total, valor_frete, valor_itens = row
        total_norm = normalize_float_value(valor_total)
        frete_norm = normalize_float_value(valor_frete)
        itens_norm = normalize_float_value(valor_itens)
        calculado = frete_norm + itens_norm
        
        # Se valor_total está consistente com frete + itens (ou se não tem frete/itens, usar valor_total)
        if abs(total_norm - calculado) < 0.01 or (frete_norm == 0 and itens_norm == 0):
            soma_consistente += total_norm
    
    print(f"R$ {soma_consistente:.2f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/diagnostico_valores.py YYYY-MM-DD")
        print("Exemplo: python scripts/diagnostico_valores.py 2025-01-05")
        sys.exit(1)
    
    data = sys.argv[1]
    diagnosticar_data(data)

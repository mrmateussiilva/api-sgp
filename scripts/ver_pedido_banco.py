#!/usr/bin/env python3
"""Verifica como os valores de um pedido estão gravados no banco"""

import sqlite3
from pathlib import Path

def get_db_path():
    shared_db = Path(__file__).parent.parent / "shared" / "db" / "banco.db"
    if shared_db.exists():
        return shared_db
    db_path = Path(__file__).parent.parent / "db" / "banco.db"
    if db_path.exists():
        return db_path
    raise FileNotFoundError("Banco de dados não encontrado")

# Conectar ao banco
db_path = get_db_path()
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row  # Para acessar colunas por nome

# Buscar pedido 50
cursor = conn.execute("""
    SELECT 
        id, numero, data_entrada, cliente,
        valor_total, valor_frete, valor_itens,
        tipo_pagamento
    FROM pedidos
    WHERE id = 50
""")

row = cursor.fetchone()

if not row:
    print("Pedido 50 não encontrado no banco de dados")
    conn.close()
    exit(1)

print("=" * 70)
print("VALORES DO PEDIDO 50 NO BANCO DE DADOS")
print("=" * 70)
print(f"\nID: {row['id']}")
print(f"Numero: {row['numero']}")
print(f"Data Entrada: {row['data_entrada']}")
print(f"Cliente: {row['cliente']}")
print(f"\nVALORES (como estão gravados no banco):")
print(f"  valor_total:  '{row['valor_total']}' (tipo: {type(row['valor_total']).__name__})")
print(f"  valor_frete:  '{row['valor_frete']}' (tipo: {type(row['valor_frete']).__name__})")
print(f"  valor_itens:  '{row['valor_itens']}' (tipo: {type(row['valor_itens']).__name__})")
print(f"  tipo_pagamento: {row['tipo_pagamento']}")

# Mostrar valores brutos
print(f"\nVALORES BRUTOS (repr):")
print(f"  valor_total:  {repr(row['valor_total'])}")
print(f"  valor_frete:  {repr(row['valor_frete'])}")
print(f"  valor_itens:  {repr(row['valor_itens'])}")

# Verificar se são None, vazios, etc
print(f"\nVERIFICAÇÕES:")
print(f"  valor_total é None: {row['valor_total'] is None}")
print(f"  valor_total == '': {row['valor_total'] == ''}")
print(f"  valor_frete é None: {row['valor_frete'] is None}")
print(f"  valor_frete == '': {row['valor_frete'] == ''}")
print(f"  valor_itens é None: {row['valor_itens'] is None}")
print(f"  valor_itens == '': {row['valor_itens'] == ''}")

# Mostrar todos os campos do pedido
print(f"\n{'=' * 70}")
print("TODOS OS CAMPOS DO PEDIDO 50")
print(f"{'=' * 70}\n")

cursor_all = conn.execute("SELECT * FROM pedidos WHERE id = 50")
row_all = cursor_all.fetchone()
columns = [description[0] for description in cursor_all.description]

for col in columns:
    value = row_all[columns.index(col)]
    # Truncar valores muito longos
    if isinstance(value, str) and len(value) > 100:
        value_display = value[:100] + "..."
    else:
        value_display = value
    print(f"  {col:30s}: {repr(value_display)}")

conn.close()

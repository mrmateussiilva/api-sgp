import sqlite3
import os

db_path = "shared/db/banco.db"
if not os.path.exists(db_path):
    print(f"CRÍTICO: Banco não encontrado em {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print(f"--- Verificando dados em {db_path} ---")
    
    # Listar tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tabelas encontradas: {[t[0] for t in tables]}")
    
    # Contar registros em algumas tabelas chaves
    tables_to_check = ['user', 'pedidos', 'clientes', 'producoes']
    for table in tables_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Tabela '{table}': {count} registros")
        except sqlite3.OperationalError:
            print(f"Tabela '{table}' não existe ou erro ao ler.")

except Exception as e:
    print(f"Erro: {e}")
finally:
    conn.close()

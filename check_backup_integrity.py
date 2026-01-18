import sqlite3
import os

db_path = "shared/backups/banco-backup-20260110-135940.db"
if not os.path.exists(db_path):
    print(f"CRÍTICO: Backup não encontrado em {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print(f"--- Verificando dados em {db_path} ---")
    
    # Listar tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tabelas: {[t[0] for t in tables]}")
    
    # Contar
    for table in ['user', 'pedidos', 'cliente', 'clientes']:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"Tabela '{table}': {cursor.fetchone()[0]} registros")
        except:
            pass

except Exception as e:
    print(f"Erro: {e}")
finally:
    conn.close()

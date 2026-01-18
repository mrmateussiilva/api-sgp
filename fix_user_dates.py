import sqlite3
import os
from datetime import datetime

db_path = "shared/db/banco.db"
if not os.path.exists(db_path):
    print(f"Banco não encontrado em {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("--- Corrigindo dados da tabela user ---")
    
    # Buscar todos os usuários
    cursor.execute("SELECT id, created_at, updated_at FROM user")
    rows = cursor.fetchall()
    
    for row in rows:
        user_id = row[0]
        created_at = row[1]
        updated_at = row[2]
        
        updates = []
        params = []
        
        # Corrigir created_at
        if isinstance(created_at, int) or (isinstance(created_at, str) and created_at.isdigit()):
            new_created = f"{created_at}-01-01 00:00:00"
            updates.append("created_at = ?")
            params.append(new_created)
            print(f"User {user_id}: Convertendo created_at {created_at} -> {new_created}")
        
        # Corrigir updated_at
        if isinstance(updated_at, int) or (isinstance(updated_at, str) and updated_at.isdigit()):
            new_updated = f"{updated_at}-01-01 00:00:00"
            updates.append("updated_at = ?")
            params.append(new_updated)
            print(f"User {user_id}: Convertendo updated_at {updated_at} -> {new_updated}")
            
        if updates:
            query = f"UPDATE user SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)
            cursor.execute(query, params)
            
    conn.commit()
    print("--- Correção concluída ---")

except Exception as e:
    print(f"Erro: {e}")
    conn.rollback()
finally:
    conn.close()

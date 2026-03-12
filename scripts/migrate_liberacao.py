import sqlite3
import os
from pathlib import Path

def migrate():
    # Caminho do banco conforme configurado no projeto
    db_path = Path("/home/mateus/Documentos/Projetcts/FinderBit/api-sgp/shared/db/banco.db")
    
    if not db_path.exists():
        print(f"Erro: Banco de dados não encontrado em {db_path}")
        return

    print(f"Conectando ao banco: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(pedidos)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "financeiro_liberado_em" in columns:
            print("Coluna 'financeiro_liberado_em' já existe na tabela 'pedidos'.")
        else:
            print("Adicionando coluna 'financeiro_liberado_em' à tabela 'pedidos'...")
            cursor.execute("ALTER TABLE pedidos ADD COLUMN financeiro_liberado_em DATETIME")
            conn.commit()
            print("Coluna adicionada com sucesso!")
            
    except Exception as e:
        print(f"Erro durante a migração: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

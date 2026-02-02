import sqlite3
import os
from pathlib import Path

def cleanup():
    # Caminho do banco
    db_path = "/home/mateus/Projetcs/api-sgp/shared/db/banco.db"
    
    if not os.path.exists(db_path):
        print(f"Erro: Banco não encontrado em {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contar antes
        cursor.execute("SELECT COUNT(*) FROM print_logs")
        before = cursor.fetchone()[0]
        
        # Deletar duplicatas (mantendo o mais recente)
        # Notas: Agrupamos por pedido_id e item_id. Se item_id for NULL, tratamos individualmente ou agrupamos?
        # Geralmente item_id NULL é log de pedido inteiro ou erro genérico.
        # Vamos agrupar por pedido_id e item_id, mas apenas para registros onde item_id não é NULL.
        
        query = """
        DELETE FROM print_logs 
        WHERE id NOT IN (
            SELECT MAX(id) 
            FROM print_logs 
            GROUP BY pedido_id, COALESCE(item_id, -1)
        );
        """
        
        cursor.execute(query)
        deleted = cursor.rowcount
        conn.commit()
        
        # Contar depois
        cursor.execute("SELECT COUNT(*) FROM print_logs")
        after = cursor.fetchone()[0]
        
        print(f"Limpeza concluída:")
        print(f" - Registros antes: {before}")
        print(f" - Registros deletados (duplicados): {deleted}")
        print(f" - Registros atuais: {after}")
        
        conn.close()
    except Exception as e:
        print(f"Erro durante a limpeza: {e}")

if __name__ == "__main__":
    cleanup()

"""
Recria a tabela de usuários com o schema correto
"""
from sqlmodel import Session, text
from database import engine

def recreate_users_table():
    """Recria a tabela user com a estrutura correta"""
    
    with Session(engine) as session:
        # Deletar tabela antiga
        session.exec(text("DROP TABLE IF EXISTS user"))
        session.commit()
        
        # Criar tabela nova com SQL direto
        session.exec(text("""
            CREATE TABLE user (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                password VARCHAR NOT NULL,
                email VARCHAR,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            )
        """))
        session.commit()
        
        # Inserir usuários padrão
        session.exec(text("""
            INSERT INTO user (name, password, is_admin) 
            VALUES ('admin', 'admin123', 1), 
                   ('usuario', 'user123', 0)
        """))
        session.commit()
        
        print("✅ Tabela user recriada com sucesso!")
        print("✅ Usuários padrão criados:")
        print("   - admin / admin123 (admin)")
        print("   - usuario / user123 (usuário)")

if __name__ == "__main__":
    recreate_users_table()



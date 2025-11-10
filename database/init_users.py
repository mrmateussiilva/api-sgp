"""
Script para inicializar usuários no banco de dados usando SQLModel
"""
from sqlmodel import Session, select
from database import engine
from admin.schema import User

def init_users():
    """Cria usuários padrão se não existirem"""
    
    with Session(engine) as session:
        # Verificar se já existem usuários
        statement = select(User)
        existing_users = session.exec(statement).all()
        
        if existing_users:
            print(f"✅ Já existem {len(existing_users)} usuários no banco")
            return
        
        # Criar usuários padrão
        admin_user = User(
            name="admin",
            password="admin123"
        )
        
        regular_user = User(
            name="usuario",
            password="user123"
        )
        
        session.add(admin_user)
        session.add(regular_user)
        session.commit()
        
        print("✅ Usuários criados:")
        print("   - admin / admin123")
        print("   - usuario / user123")

if __name__ == "__main__":
    init_users()



"""
Script para inicializar usuários no banco de dados usando SQLModel
"""
import bcrypt
from sqlmodel import Session, select
from database.database import engine
from auth.models import User

def get_password_hash(password: str) -> str:
    """Gera hash da senha"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def init_users():
    """Cria usuários padrão se não existirem"""
    
    # Usando sync_engine para operações síncronas
    with Session(engine.sync_engine) as session:
        # Verificar se já existem usuários
        statement = select(User)
        existing_users = session.exec(statement).all()
        
        if existing_users:
            print(f"✅ Já existem {len(existing_users)} usuários no banco")
            return
        
        # Criar usuários padrão
        admin_user = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            is_admin=True,
            is_active=True
        )
        
        regular_user = User(
            username="usuario",
            password_hash=get_password_hash("user123"),
            is_admin=False,
            is_active=True
        )
        
        session.add(admin_user)
        session.add(regular_user)
        session.commit()
        
        print("✅ Usuários criados:")
        print("   - admin / admin123")
        print("   - usuario / user123")

if __name__ == "__main__":
    init_users()
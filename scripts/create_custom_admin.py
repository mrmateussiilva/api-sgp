import asyncio
import os
import sys
import bcrypt
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from database.database import engine
from auth.models import User

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

async def create_admin():
    async with AsyncSession(engine) as session:
        statement = select(User).where(User.username == "admin")
        result = await session.exec(statement)
        existing_user = result.first()
        
        if existing_user:
            print("Usuário 'admin' já existe. Atualizando a senha para 'admin3010'...")
            existing_user.password_hash = get_password_hash("admin3010")
            existing_user.password_plain = "admin3010"
            existing_user.is_admin = True
            session.add(existing_user)
            await session.commit()
            print("Senha atualizada com sucesso.")
            return

        print("Criando novo usuário 'admin'...")
        admin_user = User(
            username="admin",
            password_hash=get_password_hash("admin3010"),
            password_plain="admin3010",
            is_admin=True,
            is_active=True,
            setor="geral"
        )
        session.add(admin_user)
        await session.commit()
        print("Usuário 'admin' criado com sucesso com a senha 'admin3010'.")

if __name__ == "__main__":
    asyncio.run(create_admin())

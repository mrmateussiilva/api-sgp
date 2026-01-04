import asyncio
from sqlmodel import select

from database.database import async_session_maker, create_db_and_tables
from producoes.schema import Producao


# Tipos de produção padrão do sistema
TIPOS_PRODUCAO_DEFAULT = [
    {
        "name": "painel",
        "description": "Tecido",
        "active": True,
    },
    {
        "name": "generica",
        "description": "Produção Genérica",
        "active": True,
    },
    {
        "name": "totem",
        "description": "Totem",
        "active": True,
    },
    {
        "name": "lona",
        "description": "Lona",
        "active": True,
    },
    {
        "name": "adesivo",
        "description": "Adesivo",
        "active": True,
    },
    {
        "name": "almofada",
        "description": "Almofada",
        "active": True,
    },
    {
        "name": "bolsinha",
        "description": "Bolsinha",
        "active": True,
    },
]


async def seed_producoes() -> None:
    """Popula a tabela de tipos de produção com os tipos padrão"""
    await create_db_and_tables()
    
    print("🌱 Iniciando seed de tipos de produção...")
    
    async with async_session_maker() as session:
        # Verificar quais tipos já existem
        result = await session.exec(select(Producao))
        existing_tipos = {tipo.name.lower(): tipo for tipo in result.all()}
        
        tipos_criados = 0
        tipos_existentes = 0
        
        for tipo_data in TIPOS_PRODUCAO_DEFAULT:
            tipo_name = tipo_data["name"].lower()
            
            # Se já existe, pular
            if tipo_name in existing_tipos:
                print(f"⏭️  Tipo '{tipo_data['name']}' já existe, pulando...")
                tipos_existentes += 1
                continue
            
            # Criar novo tipo
            producao = Producao(**tipo_data)
            session.add(producao)
            print(f"✅ Criando tipo: {tipo_data['name']} - {tipo_data['description']}")
            tipos_criados += 1
        
        await session.commit()
        
        print(f"\n📊 Resumo:")
        print(f"   ✅ Tipos criados: {tipos_criados}")
        print(f"   ⏭️  Tipos existentes: {tipos_existentes}")
        print(f"   📝 Total processado: {len(TIPOS_PRODUCAO_DEFAULT)}")
        print(f"\n✨ Seed de tipos de produção concluído!")


if __name__ == "__main__":
    asyncio.run(seed_producoes())


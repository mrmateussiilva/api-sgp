#!/usr/bin/env python3
"""
Teste de importação dos módulos
"""

def test_imports():
    try:
        print("🔄 Testando importações...")
        
        # Testar schema
        from pedidos.schema import Pedido, PedidoCreate, PedidoUpdate, PedidoResponse
        print("✅ Schema importado com sucesso")
        
        # Testar router
        from pedidos.router import router
        print("✅ Router importado com sucesso")
        
        # Testar database
        from database.database import get_session, create_db_and_tables
        print("✅ Database importado com sucesso")
        
        # Testar base
        from base import get_session, create_db_and_tables
        print("✅ Base importado com sucesso")
        
        print("🎉 Todas as importações funcionaram!")
        return True
        
    except Exception as e:
        print(f"❌ Erro na importação: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()



#!/usr/bin/env python3
"""
Script para fazer backup do banco de dados antes do deploy.
Execute ANTES de fazer o deploy do novo backend para preservar dados existentes.

Uso:
    python scripts/backup_before_deploy.py
"""
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from config import settings


async def backup_before_deploy():
    """Faz backup do banco de dados antes do deploy."""
    # Resolver caminho do banco
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
    elif db_url.startswith("sqlite://"):
        db_path = Path(db_url.replace("sqlite://", ""))
    else:
        print(f"❌ URL do banco não é SQLite: {db_url}")
        return None
    
    if not db_path.exists():
        print(f"⚠️  Banco de dados não encontrado em: {db_path}")
        print(f"   Isso é normal se for a primeira instalação.")
        return None
    
    # Criar diretório de backups se não existir
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Nome do backup com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.stem}_backup_{timestamp}.db"
    backup_path = backup_dir / backup_name
    
    # Copiar banco
    try:
        shutil.copy2(db_path, backup_path)
        size_mb = backup_path.stat().st_size / 1024 / 1024
        
        print(f"✅ Backup criado com sucesso!")
        print(f"   Arquivo: {backup_path}")
        print(f"   Tamanho: {size_mb:.2f} MB")
        print(f"   Original: {db_path}")
        print(f"\n💡 Guarde este backup em local seguro antes do deploy!")
        
        return backup_path
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(backup_before_deploy())


#!/usr/bin/env python3
"""
Script para migrar banco de dados e pasta media para a estrutura de releases compartilhada.

Este script move:
- db/banco.db -> shared/db/banco.db
- media/ -> shared/media/
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

def main():
    # Determinar diretório raiz
    script_dir = Path(__file__).parent
    api_root = script_dir.parent
    
    print("=" * 70)
    print("  Migração para Arquitetura de Releases Compartilhada")
    print("=" * 70)
    print()
    
    # Definir caminhos
    old_db_dir = api_root / "db"
    old_media_dir = api_root / "media"
    
    # Perguntar ao usuário onde criar a estrutura compartilhada
    # Por padrão, usar o diretório pai ou criar estrutura relativa
    print("Onde você quer criar a estrutura compartilhada?")
    print(f"1. No diretório atual ({api_root}) - shared/")
    print(f"2. Em diretório absoluto (ex: /opt/api ou C:\\api)")
    print()
    
    choice = input("Escolha (1 ou 2): ").strip()
    
    if choice == "2":
        api_root_path = input("Digite o caminho absoluto (ex: /opt/api ou C:\\api): ").strip()
        if not api_root_path:
            print("❌ Caminho vazio. Usando diretório atual.")
            api_root_path = str(api_root)
    else:
        api_root_path = str(api_root)
    
    api_root_path = Path(api_root_path).resolve()
    shared_dir = api_root_path / "shared"
    
    print()
    print(f"📁 Estrutura será criada em: {api_root_path}")
    print(f"📁 Diretório compartilhado: {shared_dir}")
    print()
    
    # Confirmar antes de prosseguir
    confirm = input("Continuar? (s/N): ").strip().lower()
    if confirm != "s":
        print("❌ Migração cancelada.")
        return 1
    
    print()
    print("🔄 Iniciando migração...")
    print()
    
    # 1. Criar estrutura de diretórios compartilhados
    print("1️⃣  Criando estrutura de diretórios compartilhados...")
    shared_dirs = {
        "db": shared_dir / "db",
        "media_pedidos": shared_dir / "media" / "pedidos",
        "media_fichas": shared_dir / "media" / "fichas",
        "media_templates": shared_dir / "media" / "templates",
        "logs": shared_dir / "logs",
        "backups": shared_dir / "backups",
    }
    
    for name, dir_path in shared_dirs.items():
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ Criado: {dir_path}")
    
    print()
    
    # 2. Migrar banco de dados
    print("2️⃣  Migrando banco de dados...")
    old_db_file = old_db_dir / "banco.db"
    new_db_file = shared_dir / "db" / "banco.db"
    
    if old_db_file.exists():
        # Fazer backup antes de mover
        backup_file = shared_dir / "backups" / f"banco-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        print(f"   💾 Fazendo backup: {backup_file}")
        shutil.copy2(old_db_file, backup_file)
        print(f"   ✅ Backup criado: {backup_file}")
        
        # Verificar se banco já existe no destino
        if new_db_file.exists():
            print(f"   ⚠️  Banco já existe em {new_db_file}")
            overwrite = input("   Deseja sobrescrever? (s/N): ").strip().lower()
            if overwrite != "s":
                print("   ⏭️  Pulando migração do banco de dados.")
                new_db_file = None
        
        if new_db_file:
            # Copiar banco
            print(f"   📦 Copiando: {old_db_file} -> {new_db_file}")
            shutil.copy2(old_db_file, new_db_file)
            print(f"   ✅ Banco copiado com sucesso!")
            
            # Copiar arquivos auxiliares do SQLite
            for ext in ["-shm", "-wal"]:
                old_aux = old_db_dir / f"banco.db{ext}"
                new_aux = shared_dir / "db" / f"banco.db{ext}"
                if old_aux.exists():
                    shutil.copy2(old_aux, new_aux)
                    print(f"   ✅ Arquivo auxiliar copiado: banco.db{ext}")
    else:
        print(f"   ⚠️  Banco de dados não encontrado: {old_db_file}")
    
    print()
    
    # 3. Migrar pasta media
    print("3️⃣  Migrando pasta media...")
    if old_media_dir.exists():
        # Copiar cada subpasta
        for item in old_media_dir.iterdir():
            if item.is_dir() and item.name not in [".", ".."]:
                dest_dir = shared_dir / "media" / item.name
                print(f"   📦 Copiando: {item.name}/ -> {dest_dir}")
                if dest_dir.exists():
                    print(f"   ⚠️  Diretório já existe: {dest_dir}")
                    merge = input(f"   Deseja mesclar (sobrescrever) {item.name}? (s/N): ").strip().lower()
                    if merge == "s":
                        shutil.rmtree(dest_dir)
                        shutil.copytree(item, dest_dir)
                        print(f"   ✅ Diretório mesclado: {item.name}")
                    else:
                        print(f"   ⏭️  Pulando: {item.name}")
                else:
                    shutil.copytree(item, dest_dir)
                    print(f"   ✅ Diretório copiado: {item.name}")
            
            elif item.is_file() and item.name != ".gitkeep":
                dest_file = shared_dir / "media" / item.name
                print(f"   📦 Copiando arquivo: {item.name}")
                shutil.copy2(item, dest_file)
                print(f"   ✅ Arquivo copiado: {item.name}")
    else:
        print(f"   ⚠️  Pasta media não encontrada: {old_media_dir}")
    
    print()
    print("=" * 70)
    print("  ✅ Migração concluída!")
    print("=" * 70)
    print()
    print("📋 Próximos passos:")
    print()
    print(f"1. Configure API_ROOT no ambiente:")
    print(f"   export API_ROOT={api_root_path}  # Linux")
    print(f"   $env:API_ROOT=\"{api_root_path}\"  # Windows PowerShell")
    print()
    print("2. Ou crie um arquivo .env na raiz do projeto:")
    print(f"   API_ROOT={api_root_path}")
    print()
    print("3. Teste a API para garantir que está usando os novos diretórios")
    print()
    print("4. Se tudo estiver funcionando, você pode remover os diretórios antigos:")
    print(f"   rm -rf {old_db_dir}  # CUIDADO! Faça backup primeiro!")
    print(f"   rm -rf {old_media_dir}  # CUIDADO! Faça backup primeiro!")
    print()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n❌ Migração cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro durante migração: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


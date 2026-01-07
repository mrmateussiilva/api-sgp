#!/usr/bin/env python3
"""
Script para criar executável da API usando PyInstaller.
Gera um único arquivo .exe que contém toda a aplicação Python.

Uso:
    python scripts/build_exe.py [versão]
    
Exemplo:
    python scripts/build_exe.py 0.1
    # Cria: dist/api_sgp_0_1.exe
"""
import subprocess
import sys
from pathlib import Path


def build_exe(version: str = "0.1"):
    """Cria executável da API usando PyInstaller."""
    exe_name = f"api_sgp_{version.replace('.', '_')}"
    
    # Lista de pastas a incluir
    folders_to_include = [
        "auth",
        "pedidos",
        "clientes",
        "pagamentos",
        "envios",
        "admin",
        "materiais",
        "designers",
        "vendedores",
        "producoes",
        "users",
        "notificacoes",
        "fichas",
        "relatorios",
        "database",
    ]
    
    # Construir comandos --add-data
    add_data_args = []
    for folder in folders_to_include:
        add_data_args.extend(["--add-data", f"{folder};{folder}"])
    
    # Adicionar arquivos importantes
    add_data_args.extend(["--add-data", "config.py;."])
    add_data_args.extend(["--add-data", "base.py;."])
    add_data_args.extend(["--add-data", "logging_config.py;."])
    
    # Comando PyInstaller
    cmd = [
        "pyinstaller",
        "--name", exe_name,
        "--onefile",  # Um único arquivo .exe
        "--console",  # Mostrar console (útil para logs)
        "--clean",  # Limpar cache antes de build
        *add_data_args,
        # Imports ocultos necessários
        "--hidden-import", "uvicorn",
        "--hidden-import", "hypercorn",
        "--hidden-import", "fastapi",
        "--hidden-import", "sqlmodel",
        "--hidden-import", "aiosqlite",
        "--hidden-import", "orjson",
        "--hidden-import", "aiofiles",
        "--hidden-import", "bcrypt",
        "--hidden-import", "jose",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_settings",
        "--hidden-import", "starlette",
        "--hidden-import", "asyncio",
        "--hidden-import", "sqlalchemy",
        "--hidden-import", "sqlalchemy.ext.asyncio",
        # Arquivo principal
        "main.py"
    ]
    
    print(f"🔨 Criando executável: {exe_name}.exe")
    print(f"   Versão: {version}")
    print(f"   Comando: pyinstaller --name {exe_name} --onefile --console ...")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        
        if result.returncode == 0:
            exe_path = Path("dist") / f"{exe_name}.exe"
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / 1024 / 1024
                print()
                print(f"✅ Executável criado com sucesso!")
                print(f"   Arquivo: {exe_path}")
                print(f"   Tamanho: {size_mb:.2f} MB")
                print()
                print(f"💡 Próximos passos:")
                print(f"   1. Copie o executável para o servidor")
                print(f"   2. Crie os diretórios: db, media, logs, backups")
                print(f"   3. Configure o NSSM para usar o executável")
                return exe_path
            else:
                print(f"⚠️  Executável não encontrado em: {exe_path}")
                print(f"   Verifique a pasta dist/")
                return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao criar executável: {e}")
        print(f"   Certifique-se de que PyInstaller está instalado:")
        print(f"   pip install pyinstaller")
        return None
    except FileNotFoundError:
        print(f"❌ PyInstaller não encontrado!")
        print(f"   Instale com: pip install pyinstaller")
        return None


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else "0.1"
    build_exe(version)


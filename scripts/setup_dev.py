import os
import sys
import subprocess
from pathlib import Path

# Add project root to python path
sys.path.append(str(Path(__file__).parent.parent))

def run_command(command, cwd=None, env=None):
    """Executa um comando no shell e imprime a saída."""
    print(f"🔄 Executando: {command}")
    try:
        subprocess.check_call(command, shell=True, cwd=cwd, env=env)
        print("✅ Sucesso!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar comando: {e}")
        sys.exit(1)

def main():
    print("🚀 Configurando ambiente de desenvolvimento...")

    # 1. Definir conteúdo do .env
    env_content = (
        "DATABASE_URL=sqlite:///db/dev.db\n"
        "API_ROOT=.\n"
        "MEDIA_ROOT=media\n"
        "LOG_DIR=logs\n"
    )
    
    # 2. Configurar .env
    env_path = Path(".env")
    if env_path.exists():
        # Verificar se já é o de dev
        with open(env_path, "r") as f:
            content = f.read()
        if "sqlite:///db/dev.db" not in content:
            print("⚠️  Arquivo .env já existe e não parece ser o de dev.")
            print("   Fazendo backup para .env.bkp e criando novo .env...")
            import shutil
            shutil.copy(".env", ".env.bkp")
            with open(".env", "w") as f:
                f.write(env_content)
        else:
            print("✅ Arquivo .env já está configurado para dev.")
    else:
        print("📝 Criando arquivo .env...")
        with open(".env", "w") as f:
            f.write(env_content)

    # 3. Preparar ambiente (variáveis) para os sub-processos
    # Precisamos garantir que os subprocessos vejam as variáveis corretas
    # O python-dotenv vai ler o .env que acabamos de criar, mas podemos forçar aqui também
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///db/dev.db"
    env["API_ROOT"] = "."
    env["MEDIA_ROOT"] = "media"

    # 4. Criar diretórios
    dirs = ["db", "media/pedidos", "media/fichas", "media/templates", "logs"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("📂 Diretórios verificados.")

    # 5. Inicializar Banco de Dados (Criar tabelas)
    print("🏗️  Criando tabelas no banco de dados...")
    # Usando subprocesso para garantir isolamento do contexto de importação
    run_command(f"{sys.executable} -c \"from base import create_db_and_tables; import asyncio; asyncio.run(create_db_and_tables())\"", env=env)

    # 6. Criar Usuários Iniciais
    print("👤 Criando usuários iniciais...")
    # init_users.py está em database/init_users.py
    run_command(f"{sys.executable} database/init_users.py", env=env)

    # 7. Popular Pedidos
    print("🌱 Semeando banco de dados com pedidos de teste...")
    run_command(f"{sys.executable} scripts/seed_pedidos.py --amount 20", env=env)

    print("\n✅ Ambiente de desenvolvimento configurado com sucesso!")
    print("\nPara iniciar o servidor:")
    print("  uvicorn main:app --reload --host 0.0.0.0 --port 8000")

if __name__ == "__main__":
    main()
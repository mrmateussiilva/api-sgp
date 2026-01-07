# Deploy com Executável (.exe)

Este guia explica como criar e usar um executável da API SGP para facilitar o deploy no Windows Server.

## 📦 Vantagens do Executável

- ✅ **Sem necessidade de Python instalado** no servidor
- ✅ **Todas as dependências incluídas** no .exe
- ✅ **Deploy simplificado** - apenas copiar o .exe
- ✅ **Versões fáceis de gerenciar** - `api_sgp_0_1.exe`, `api_sgp_0_2.exe`, etc.
- ✅ **Menos configuração** - não precisa configurar Python, pip, etc.

## 🔨 Criar o Executável

### Pré-requisitos

1. **Python 3.12+** instalado (apenas para criar o executável)
2. **PyInstaller** instalado:
   ```bash
   pip install pyinstaller
   ```

### Opção 1: Script PowerShell (Recomendado)

```powershell
# Criar executável versão 0.1
.\scripts\build_exe.ps1 -Version 0.1

# Criar executável versão 0.2
.\scripts\build_exe.ps1 -Version 0.2
```

### Opção 2: Script Python

```bash
# Criar executável versão 0.1
python scripts/build_exe.py 0.1

# Criar executável versão 0.2
python scripts/build_exe.py 0.2
```

### Resultado

O executável será criado em `dist/api_sgp_0_1.exe` (ou versão especificada).

**Tamanho esperado:** ~50-100 MB (depende das dependências)

## 🚀 Deploy do Executável

### 1. Preparar o Servidor

1. **Copiar o executável** para o servidor (ex: `C:\SGP\api_sgp_0_1.exe`)
2. **Criar diretórios necessários**:
   ```powershell
   cd C:\SGP
   mkdir db, media, logs, backups
   ```

3. **Copiar banco de dados existente** (se houver):
   ```powershell
   # ANTES de fazer o deploy, faça backup!
   python scripts/backup_before_deploy.py
   
   # Copie o banco existente para o diretório db/
   copy C:\BackendAntigo\db\banco.db C:\SGP\db\banco.db
   ```

### 2. Deploy Automatizado com Script

```powershell
# Deploy com executável
.\scripts\deploy.ps1 `
  -UseExe `
  -ExePath "C:\SGP\api_sgp_0_1.exe" `
  -Port 8000 `
  -Workers 4
```

### 3. Deploy Manual com NSSM

```powershell
# Instalar serviço
nssm install SGP-API "C:\SGP\api_sgp_0_1.exe" "--bind 0.0.0.0:8000 --workers 4"

# Configurar diretório de trabalho
nssm set SGP-API AppDirectory "C:\SGP"

# Configurar logs
nssm set SGP-API AppStdout "C:\SGP\logs\stdout.log"
nssm set SGP-API AppStderr "C:\SGP\logs\stderr.log"

# Iniciar serviço
nssm start SGP-API
```

### 4. Executar Diretamente (Teste)

```powershell
# Executar diretamente para testar
.\api_sgp_0_1.exe --bind 0.0.0.0:8000 --workers 4

# Ou sem workers
.\api_sgp_0_1.exe --bind 0.0.0.0:8000
```

## 📋 Argumentos do Executável

O executável aceita os seguintes argumentos:

- `--bind ADDRESS:PORT` - Endereço e porta (ex: `0.0.0.0:8000`)
- `--workers N` - Número de workers (0 = sem workers, usa Uvicorn)
- `--loop LOOP` - Event loop (`asyncio` ou `uvloop`, default: `asyncio`)

**Exemplos:**

```powershell
# Com 4 workers (Hypercorn)
.\api_sgp_0_1.exe --bind 0.0.0.0:8000 --workers 4

# Sem workers (Uvicorn)
.\api_sgp_0_1.exe --bind 0.0.0.0:8000

# Porta diferente
.\api_sgp_0_1.exe --bind 0.0.0.0:8080 --workers 2
```

## 💾 Preservar Banco de Dados

### ⚠️ IMPORTANTE: Backup Antes do Deploy

**SEMPRE faça backup do banco antes de fazer deploy:**

```bash
# No servidor antigo, antes de parar o serviço
python scripts/backup_before_deploy.py
```

Isso criará um backup em `backups/banco_backup_YYYYMMDD_HHMMSS.db`

### Migração do Banco

1. **Parar o serviço antigo**:
   ```powershell
   Stop-Service SGP-API-Old
   ```

2. **Fazer backup**:
   ```powershell
   python scripts/backup_before_deploy.py
   ```

3. **Copiar banco para novo diretório**:
   ```powershell
   copy C:\BackendAntigo\db\banco.db C:\SGP\db\banco.db
   ```

4. **Iniciar novo serviço**:
   ```powershell
   Start-Service SGP-API
   ```

5. **Verificar se dados estão preservados**:
   ```powershell
   # Testar API
   Invoke-WebRequest http://localhost:8000/health
   ```

### Como Funciona a Preservação

O código foi modificado para **NÃO recriar tabelas existentes**:

- Se o banco já existe com tabelas → apenas verifica novas tabelas
- Se o banco é novo → cria todas as tabelas
- **Dados existentes são preservados automaticamente**

## 🔄 Atualizar Versão

Para atualizar para uma nova versão:

1. **Criar novo executável**:
   ```powershell
   .\scripts\build_exe.ps1 -Version 0.2
   ```

2. **Parar serviço atual**:
   ```powershell
   Stop-Service SGP-API
   ```

3. **Substituir executável**:
   ```powershell
   copy dist\api_sgp_0_2.exe C:\SGP\api_sgp_0_2.exe
   ```

4. **Atualizar serviço NSSM**:
   ```powershell
   nssm set SGP-API Application "C:\SGP\api_sgp_0_2.exe"
   ```

5. **Iniciar serviço**:
   ```powershell
   Start-Service SGP-API
   ```

## 📁 Estrutura de Diretórios

Após o deploy, a estrutura deve ser:

```
C:\SGP\
├── api_sgp_0_1.exe      # Executável
├── db\
│   └── banco.db         # Banco de dados (preservado do deploy anterior)
├── media\               # Arquivos de mídia
├── logs\                # Logs do serviço
│   ├── stdout.log
│   └── stderr.log
└── backups\             # Backups do banco
    └── banco_backup_*.db
```

## 🐛 Troubleshooting

### Executável não inicia

1. **Verificar logs**:
   ```powershell
   Get-Content C:\SGP\logs\stderr.log
   ```

2. **Executar manualmente** para ver erros:
   ```powershell
   .\api_sgp_0_1.exe --bind 0.0.0.0:8000
   ```

3. **Verificar diretórios**:
   ```powershell
   # Garantir que existem
   Test-Path C:\SGP\db
   Test-Path C:\SGP\media
   ```

### Banco de dados não encontrado

O executável cria automaticamente o diretório `db/` se não existir, mas o banco precisa ser copiado manualmente.

### Erro de permissões

Execute o NSSM como Administrador:
```powershell
Start-Process powershell -Verb RunAs
```

## 📝 Notas

- O executável é **auto-contido** - não precisa de Python instalado
- O banco de dados é **preservado automaticamente** - não será apagado
- Logs são salvos em `logs/` no diretório do executável
- Backups devem ser feitos **antes** de cada deploy


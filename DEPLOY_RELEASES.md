# 🏗️ Arquitetura de Releases Versionadas - API SGP

Este documento descreve a arquitetura de releases versionadas implementada para a API SGP, permitindo deploy, rollback e gerenciamento de múltiplas versões de forma isolada, enquanto mantém dados compartilhados.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Estrutura de Diretórios](#estrutura-de-diretórios)
- [Como Funciona](#como-funciona)
- [Deploy no Windows](#deploy-no-windows)
- [Deploy no Linux](#deploy-no-linux)
- [Gerenciamento de Releases](#gerenciamento-de-releases)
- [Banco de Dados Compartilhado](#banco-de-dados-compartilhado)
- [Migrações e Atualizações](#migrações-e-atualizações)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

A arquitetura de releases versionadas oferece:

✅ **Isolamento de Versões**: Cada versão roda em seu próprio diretório com ambiente virtual isolado  
✅ **Banco de Dados Compartilhado**: Todas as versões compartilham o mesmo banco de dados  
✅ **Rollback Rápido**: Voltar para versão anterior em segundos  
✅ **Sem Downtime**: Deploy sem interrupção de serviço  
✅ **Histórico de Versões**: Mantém histórico de releases para referência  
✅ **Backup Centralizado**: Banco de dados e arquivos media em local único  

## 📁 Estrutura de Diretórios

```
C:\api\                    # (Windows) ou /opt/api (Linux)
├── releases\              # Versões isoladas da API
│   ├── v1.0.4\           # Versão antiga (pode ser removida)
│   │   ├── venv\         # Ambiente virtual isolado
│   │   ├── main.py       # Código da API
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   ├── .env          # Config apontando para shared/
│   │   └── ...
│   ├── v1.0.5\           # Versão atual
│   │   ├── venv\         # Ambiente virtual isolado
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   ├── .env
│   │   └── ...
│   └── current -> v1.0.5 # Link simbólico para versão ativa
│
├── shared\                # COMPARTILHADO por todas as versões
│   ├── db\
│   │   ├── banco.db      # Banco SQLite único
│   │   ├── banco.db-shm  # Arquivos temporários SQLite
│   │   └── banco.db-wal
│   ├── media\            # Arquivos media compartilhados
│   │   ├── pedidos\      # JSONs dos pedidos
│   │   ├── fichas\       # Imagens e arquivos de fichas
│   │   └── templates\    # Templates HTML
│   └── logs\             # Logs centralizados
│       ├── service_stdout.log
│       ├── service_stderr.log
│       └── api.log
│
└── backups\               # Backups do banco de dados
    ├── banco-2026-01-10.db
    └── banco-2026-01-09.db
```

## 🔧 Como Funciona

### 1. Diretórios Compartilhados

**Banco de Dados**: Todas as versões usam o mesmo banco SQLite em `shared/db/banco.db`

**Media**: Todos os arquivos de pedidos, fichas e templates são armazenados em `shared/media/`

**Logs**: Todos os logs são centralizados em `shared/logs/`

### 2. Isolamento de Versões

Cada versão tem:
- Seu próprio ambiente virtual Python (`venv/`)
- Seu próprio código (copiado no momento do deploy)
- Sua própria configuração `.env` (mas apontando para `shared/`)

### 3. Link Simbólico "current"

O link simbólico `releases/current` sempre aponta para a versão ativa:
- Deploy: `current` → `v1.0.5`
- Rollback: `current` → `v1.0.4`

O serviço Windows/Linux sempre executa a versão apontada por `current`.

### 4. Configuração via Variável de Ambiente

A variável de ambiente `API_ROOT` é configurada no serviço:
- **Windows**: Via NSSM (`AppEnvironmentExtra`)
- **Linux**: Via systemd (`Environment`)

O `main.py` detecta `API_ROOT` e configura automaticamente:
- `DATABASE_URL` → `sqlite:///{API_ROOT}/shared/db/banco.db`
- `MEDIA_ROOT` → `{API_ROOT}/shared/media`
- `LOG_DIR` → `{API_ROOT}/shared/logs`

## 🪟 Deploy no Windows

### Pré-requisitos

1. **PowerShell** (versão 5.1+)
2. **uv** instalado: `cargo install uv`
3. **NSSM** instalado (para serviço Windows)
4. **Executar como Administrador** (para instalar serviço)

### Script de Deploy

```powershell
# Deploy da versão 1.0.5
.\scripts\deploy-releases.ps1 -Version "1.0.5" -Action "deploy" -ApiRoot "C:\api" -ServiceName "SGP-API" -Port 8000

# Rollback para versão 1.0.4
.\scripts\deploy-releases.ps1 -Action "rollback" -RollbackVersion "1.0.4" -ServiceName "SGP-API"

# Listar releases disponíveis
.\scripts\deploy-releases.ps1 -Action "list" -ApiRoot "C:\api"

# Ver status do sistema
.\scripts\deploy-releases.ps1 -Action "status" -ApiRoot "C:\api" -ServiceName "SGP-API"
```

### Processo de Deploy

1. **Criar estrutura de diretórios compartilhados** (se não existir)
2. **Criar diretório da release** (`releases/v1.0.5/`)
3. **Copiar arquivos** da API (excluindo `db/`, `media/`, `logs/`, `venv/`)
4. **Criar ambiente virtual** isolado (`venv/`)
5. **Instalar dependências** com `uv pip install`
6. **Criar arquivo `.env`** apontando para `shared/`
7. **Atualizar link simbólico** `current` → `v1.0.5`
8. **Atualizar serviço Windows** via NSSM
9. **Reiniciar serviço**

### Serviço Windows (NSSM)

O script configura automaticamente o serviço Windows com:
- **Executável**: `{release}/venv/Scripts/python.exe`
- **Comando**: `-m uvicorn main:app --host 0.0.0.0 --port 8000`
- **Diretório**: `{release}/`
- **Variáveis de Ambiente**:
  - `API_ROOT=C:\api`
  - `PYTHONPATH={release}/`
  - `PORT=8000`
- **Logs**: Redirecionados para `shared/logs/service_*.log`

## 🐧 Deploy no Linux

### Pré-requisitos

1. **make** instalado
2. **uv** instalado: `cargo install uv`
3. **rsync** instalado (para copiar arquivos)
4. **Executar como root** (para instalar serviço systemd)

### Makefile

```bash
# Deploy da versão 1.0.5
sudo make deploy VERSION=1.0.5 API_ROOT=/opt/api SERVICE_NAME=sgp-api PORT=8000

# Rollback para versão 1.0.4
sudo make rollback VERSION=1.0.4 SERVICE_NAME=sgp-api

# Listar releases disponíveis
make list API_ROOT=/opt/api

# Ver status do sistema
sudo make status API_ROOT=/opt/api SERVICE_NAME=sgp-api

# Limpar releases antigas (mantém últimas 5)
make clean API_ROOT=/opt/api
```

### Processo de Deploy

1. Verificar `uv` instalado
2. Criar estrutura de diretórios compartilhados
3. Copiar arquivos com `rsync` (excluindo diretórios específicos)
4. Criar ambiente virtual com `uv venv`
5. Instalar dependências com `uv pip install`
6. Criar arquivo `.env`
7. Atualizar link simbólico `current`
8. Instalar serviço systemd
9. Reiniciar serviço

### Serviço systemd

O Makefile cria automaticamente `/etc/systemd/system/sgp-api.service`:

```ini
[Unit]
Description=SGP API - Sistema de Gestão de Produção v1.0.5
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/api/releases/current
Environment="API_ROOT=/opt/api"
Environment="PYTHONPATH=/opt/api/releases/current"
Environment="PORT=8000"
ExecStart=/opt/api/releases/current/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/opt/api/shared/logs/service_stdout.log
StandardError=append:/opt/api/shared/logs/service_stderr.log

[Install]
WantedBy=multi-user.target
```

## 📊 Gerenciamento de Releases

### Listar Releases

**Windows:**
```powershell
.\scripts\deploy-releases.ps1 -Action "list" -ApiRoot "C:\api"
```

**Linux:**
```bash
make list API_ROOT=/opt/api
```

**Saída:**
```
[INFO] Releases disponíveis:
[ATIVA] v1.0.5
        v1.0.4
        v1.0.3
```

### Status do Sistema

**Windows:**
```powershell
.\scripts\deploy-releases.ps1 -Action "status" -ApiRoot "C:\api" -ServiceName "SGP-API"
```

**Linux:**
```bash
sudo make status API_ROOT=/opt/api SERVICE_NAME=sgp-api
```

**Saída:**
```
========================================
  Status do Sistema de Releases
========================================

📁 API Root: C:\api
📁 Releases: C:\api\releases
📁 Shared: C:\api\shared

[INFO] Releases disponíveis:
[ATIVA] v1.0.5
        v1.0.4

🔧 Serviço 'SGP-API': Running
```

### Rollback

**Windows:**
```powershell
# Parar serviço
Stop-Service -Name "SGP-API"

# Rollback
.\scripts\deploy-releases.ps1 -Action "rollback" -RollbackVersion "1.0.4" -ServiceName "SGP-API"
```

**Linux:**
```bash
# Rollback
sudo make rollback VERSION=1.0.4 SERVICE_NAME=sgp-api
```

O rollback:
1. Atualiza `current` → `v1.0.4`
2. Reinicia o serviço
3. O serviço automaticamente executa a versão antiga

### Limpar Releases Antigas

**Linux:**
```bash
# Manter apenas as últimas 5 releases (mais a ativa)
make clean API_ROOT=/opt/api
```

## 💾 Banco de Dados Compartilhado

### Localização

O banco de dados está sempre em: `{API_ROOT}/shared/db/banco.db`

### Migrações Automáticas

O SQLModel cria automaticamente novas tabelas quando necessário:
- **Preserva dados existentes**: Não recria tabelas que já existem
- **Cria novas tabelas**: Se o schema foi atualizado, cria novas tabelas
- **Sem perda de dados**: Todos os dados são preservados

### Backup

**Recomendado**: Fazer backup antes de cada deploy:

```powershell
# Windows
$backupDir = "C:\api\shared\backups"
$backupFile = "$backupDir\banco-$(Get-Date -Format 'yyyy-MM-dd-HHmmss').db"
Copy-Item "C:\api\shared\db\banco.db" $backupFile
```

```bash
# Linux
BACKUP_DIR="/opt/api/shared/backups"
BACKUP_FILE="$BACKUP_DIR/banco-$(date +%Y-%m-%d-%H%M%S).db"
cp /opt/api/shared/db/banco.db "$BACKUP_FILE"
```

### Restaurar Backup

```powershell
# Windows
Stop-Service -Name "SGP-API"
Copy-Item "C:\api\shared\backups\banco-2026-01-10.db" "C:\api\shared\db\banco.db"
Start-Service -Name "SGP-API"
```

```bash
# Linux
sudo systemctl stop sgp-api
sudo cp /opt/api/shared/backups/banco-2026-01-10.db /opt/api/shared/db/banco.db
sudo systemctl start sgp-api
```

## 🔄 Migrações e Atualizações

### Atualizar Código

Quando você atualiza o código da API:

1. **Desenvolver e testar** localmente
2. **Fazer backup** do banco de dados
3. **Deploy da nova versão**:
   ```powershell
   # Windows
   .\scripts\deploy-releases.ps1 -Version "1.0.6" -Action "deploy"
   ```
   ```bash
   # Linux
   sudo make deploy VERSION=1.0.6
   ```
4. **Verificar logs** para garantir que está funcionando
5. **Se houver problemas**: Rollback imediato

### Mudanças no Schema

Se você alterou o schema do banco (adicionou campos, tabelas, etc.):

1. **Backup obrigatório** do banco antes do deploy
2. **SQLModel cria automaticamente** novas tabelas/campos
3. **Verificar logs** após deploy para confirmar criação
4. **Testar aplicação** para garantir compatibilidade

### Mudanças Incompatíveis

Se a nova versão tem mudanças incompatíveis:

1. **Planejar migração** de dados antes do deploy
2. **Criar script de migração** (`scripts/migrate_*.py`)
3. **Executar script** após deploy da nova versão
4. **Validar dados** após migração

## 🐛 Troubleshooting

### Problema: Serviço não inicia após deploy

**Solução:**
1. Verificar logs: `shared/logs/service_stderr.log`
2. Verificar se `API_ROOT` está configurado corretamente
3. Verificar se `venv` foi criado corretamente
4. Testar manualmente:
   ```powershell
   # Windows
   cd C:\api\releases\current
   .\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   ```bash
   # Linux
   cd /opt/api/releases/current
   . venv/bin/activate
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### Problema: Banco de dados não encontrado

**Solução:**
1. Verificar se `shared/db/banco.db` existe
2. Verificar permissões do diretório `shared/`
3. Verificar variável de ambiente `API_ROOT` no serviço:
   ```powershell
   # Windows (NSSM)
   nssm get SGP-API AppEnvironmentExtra
   ```
   ```bash
   # Linux (systemd)
   systemctl show sgp-api | grep Environment
   ```

### Problema: Link simbólico "current" quebrado

**Solução:**
```powershell
# Windows
cd C:\api\releases
Remove-Item current -Force
New-Item -ItemType SymbolicLink -Path current -Target v1.0.5
```

```bash
# Linux
cd /opt/api/releases
rm -f current
ln -s v1.0.5 current
```

### Problema: Erro "uv não encontrado"

**Solução:**
```bash
# Instalar uv
cargo install uv

# Verificar instalação
uv --version
```

### Problema: Permissões negadas ao criar diretórios

**Solução:**
```powershell
# Windows - Executar como Administrador
```

```bash
# Linux - Executar como root
sudo make deploy VERSION=1.0.5
```

### Problema: Rollback não funciona

**Solução:**
1. Verificar se a versão de rollback existe: `releases/v1.0.4/`
2. Verificar se o serviço foi reiniciado
3. Verificar logs após rollback
4. Testar manualmente a versão antiga

## 📝 Notas Importantes

1. **Sempre faça backup** antes de cada deploy
2. **Teste em ambiente de desenvolvimento** antes de produção
3. **Mantenha pelo menos 2-3 versões** para rollback rápido
4. **Monitore logs** após cada deploy
5. **Valide dados** após migrações de schema
6. **API_ROOT deve ser absoluto**: `C:\api` ou `/opt/api` (não relativo)
7. **Todas as versões compartilham o banco**: Cuidado com mudanças incompatíveis

## 🔗 Referências

- [NSSM - Non-Sucking Service Manager](https://nssm.cc/)
- [systemd Service Unit](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [uv - Fast Python Package Installer](https://github.com/astral-sh/uv)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)


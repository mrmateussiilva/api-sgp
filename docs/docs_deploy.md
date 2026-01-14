# Deploy com NSSM - Guia Rápido

Este guia mostra como configurar a API SGP como serviço Windows usando NSSM (Non-Sucking Service Manager).

## 📋 Pré-requisitos

- Windows Server ou Windows 10/11
- Python 3.12+ instalado e no PATH
- NSSM instalado (baixe em: https://nssm.cc/download)
- Executar PowerShell como **Administrador**

## 🚀 Instalação Rápida

### 1. Preparar o Ambiente

```powershell
# Navegar até o diretório do projeto
cd C:\SGP\api-sgp

# Criar diretórios necessários (se não existirem)
mkdir db, media, logs, backups -Force

# Instalar dependências
pip install -r requirements.txt
```

### 2. Instalar NSSM (se ainda não tiver)

```powershell
# Baixar NSSM
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$tempDir = "$env:TEMP\nssm_install"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Invoke-WebRequest -Uri $nssmUrl -OutFile "$tempDir\nssm.zip" -UseBasicParsing
Expand-Archive -Path "$tempDir\nssm.zip" -DestinationPath $tempDir -Force

# Copiar para Program Files
$nssmExe = Get-ChildItem -Path $tempDir -Recurse -Filter "nssm.exe" | Select-Object -First 1
$nssmTarget = "$env:ProgramFiles\NSSM\nssm.exe"
New-Item -ItemType Directory -Path (Split-Path $nssmTarget) -Force | Out-Null
Copy-Item $nssmExe.FullName $nssmTarget -Force

# Adicionar ao PATH (opcional)
$env:Path += ";$env:ProgramFiles\NSSM"
[Environment]::SetEnvironmentVariable("Path", $env:Path, [EnvironmentVariableTarget]::Machine)
```

### 3. Criar o Serviço com NSSM

#### Opção A: Usando Python diretamente (Recomendado)

```powershell
# Definir variáveis
$ServiceName = "SGP-API"
$ProjectPath = "C:\SGP\api-sgp"
$PythonPath = "python.exe"  # ou caminho completo: "C:\Python312\python.exe"
$Port = 8000
$Workers = 4

# Instalar serviço
nssm install $ServiceName $PythonPath "-m hypercorn main:app --bind 0.0.0.0:$Port --workers $Workers --loop asyncio"

# Configurar diretório de trabalho
nssm set $ServiceName AppDirectory $ProjectPath

# Configurar nome e descrição
nssm set $ServiceName DisplayName "SGP API Server"
nssm set $ServiceName Description "API Sistema de Gestão de Produção (SGP)"

# Configurar logs
nssm set $ServiceName AppStdout "$ProjectPath\logs\service_stdout.log"
nssm set $ServiceName AppStderr "$ProjectPath\logs\service_stderr.log"

# Configurar para iniciar automaticamente
nssm set $ServiceName Start SERVICE_AUTO_START

# Iniciar serviço
nssm start $ServiceName
```

#### Opção B: Usando Executável .exe

```powershell
# Definir variáveis
$ServiceName = "SGP-API"
$ExePath = "C:\SGP\api_sgp_0_1.exe"
$ProjectPath = "C:\SGP"
$Port = 8000
$Workers = 4

# Instalar serviço
nssm install $ServiceName $ExePath "--bind 0.0.0.0:$Port --workers $Workers"

# Configurar diretório de trabalho
nssm set $ServiceName AppDirectory $ProjectPath

# Configurar logs
nssm set $ServiceName AppStdout "$ProjectPath\logs\stdout.log"
nssm set $ServiceName AppStderr "$ProjectPath\logs\stderr.log"

# Configurar para iniciar automaticamente
nssm set $ServiceName Start SERVICE_AUTO_START

# Iniciar serviço
nssm start $ServiceName
```

## 🔧 Gerenciar o Serviço

### Comandos Básicos

```powershell
# Iniciar serviço
nssm start SGP-API
# ou
Start-Service SGP-API

# Parar serviço
nssm stop SGP-API
# ou
Stop-Service SGP-API

# Reiniciar serviço
nssm restart SGP-API
# ou
Restart-Service SGP-API

# Ver status
Get-Service SGP-API

# Ver logs em tempo real
Get-Content C:\SGP\api-sgp\logs\service_stdout.log -Wait -Tail 50
```

### Editar Configurações

```powershell
# Abrir interface gráfica do NSSM
nssm edit SGP-API

# Ou editar via linha de comando
nssm set SGP-API AppParameters "--bind 0.0.0.0:8080 --workers 2"
```

### Remover Serviço

```powershell
# Parar e remover
nssm stop SGP-API
nssm remove SGP-API confirm
```

## 📊 Verificar se Está Funcionando

```powershell
# Verificar status do serviço
Get-Service SGP-API

# Testar endpoint de saúde
Invoke-WebRequest http://localhost:8000/health

# Ver documentação
Start-Process http://localhost:8000/docs
```

## 🔄 Atualizar a API

### Processo Seguro de Atualização

```powershell
# 1. Fazer backup do banco ANTES de tudo
python scripts\backup_database.py --dest backups\db --retention 10

# 2. Parar o serviço
Stop-Service SGP-API

# 3. Atualizar código (Git ou copiar arquivos)
# git pull origin main
# OU copiar arquivos novos manualmente

# 4. Atualizar dependências (se necessário)
pip install -r requirements.txt --upgrade

# 5. Reiniciar serviço
Start-Service SGP-API

# 6. Verificar logs
Get-Content C:\SGP\api-sgp\logs\service_stdout.log -Tail 50
```

**⚠️ IMPORTANTE:** 
- **NUNCA** substitua o arquivo `db\banco.db` - ele contém seus dados!
- **SEMPRE** faça backup antes de atualizar
- O sistema preserva dados automaticamente ao criar novas tabelas

## 🐛 Troubleshooting

### Serviço não inicia

```powershell
# Ver logs de erro
Get-Content C:\SGP\api-sgp\logs\service_stderr.log -Tail 100

# Testar manualmente
cd C:\SGP\api-sgp
python main.py --bind 0.0.0.0:8000 --workers 4
```

### Verificar configuração do serviço

```powershell
# Ver todas as configurações
nssm get SGP-API AppParameters
nssm get SGP-API AppDirectory
nssm get SGP-API AppStdout
```

### Porta já em uso

```powershell
# Verificar qual processo está usando a porta
netstat -ano | findstr :8000

# Parar processo (substitua PID pelo número encontrado)
taskkill /PID <PID> /F
```

## 📝 Configurações Recomendadas

### Número de Workers

- **CPU 2-4 cores**: 2-3 workers
- **CPU 4-8 cores**: 4-6 workers
- **CPU 8+ cores**: 6-8 workers

### Recuperação Automática

```powershell
# Configurar para reiniciar automaticamente em caso de falha
nssm set SGP-API AppRestartDelay 5000
nssm set SGP-API AppExit Default Restart
```

## 🔐 Segurança

### Configurar SECRET_KEY para Produção

```powershell
# Criar arquivo .env no diretório do projeto
$secretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
@"
SECRET_KEY=$secretKey
ENVIRONMENT=production
"@ | Out-File -FilePath "$ProjectPath\.env" -Encoding utf8
```

## 📚 Referências

- NSSM: https://nssm.cc/
- Documentação da API: http://localhost:8000/docs
- Scripts de backup: `scripts\backup_database.py`


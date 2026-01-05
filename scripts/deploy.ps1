<#
.SYNOPSIS
    Script de deploy automatizado para API SGP no Windows Server.

.DESCRIPTION
    Este script automatiza todo o processo de deploy da API SGP:
    - Verifica pré-requisitos (Python, pip, NSSM)
    - Instala dependências Python
    - Cria diretórios necessários
    - Configura variáveis de ambiente (opcional)
    - Instala e configura como serviço Windows usando NSSM
    - Inicia o serviço

.PARAMETER ProjectPath
    Caminho do projeto (default: diretório atual)

.PARAMETER PythonPath
    Caminho do executável Python (default: python.exe no PATH)

.PARAMETER ServiceName
    Nome do serviço Windows (default: SGP-API)

.PARAMETER Port
    Porta para o servidor (default: 8000)

.PARAMETER Workers
    Número de workers (default: 4, use 0 para Uvicorn sem workers)

.PARAMETER UseHypercorn
    Usar Hypercorn ao invés de Uvicorn (default: $true)

.PARAMETER NSSMPath
    Caminho do NSSM (default: nssm.exe no PATH ou baixa automaticamente)

.PARAMETER InstallNSSM
    Baixar e instalar NSSM automaticamente se não encontrado (default: $true)

.PARAMETER CreateEnvFile
    Criar arquivo .env com configurações padrão (default: $false)

.PARAMETER SecretKey
    SECRET_KEY para produção (opcional, será gerado se não fornecido)

.PARAMETER SkipServiceInstall
    Pular instalação do serviço (apenas instalar dependências) (default: $false)

.EXAMPLE
    .\deploy.ps1 -Workers 4 -Port 8000

.EXAMPLE
    .\deploy.ps1 -ProjectPath "C:\SGP\api-sgp" -Workers 2 -UseHypercorn $false
#>
param(
    [Parameter()][string]$ProjectPath = (Get-Location).Path,
    [Parameter()][string]$PythonPath = "python.exe",
    [Parameter()][string]$ServiceName = "SGP-API",
    [Parameter()][int]$Port = 8000,
    [Parameter()][int]$Workers = 4,
    [Parameter()][bool]$UseHypercorn = $true,
    [Parameter()][string]$NSSMPath = "nssm.exe",
    [Parameter()][bool]$InstallNSSM = $true,
    [Parameter()][bool]$CreateEnvFile = $false,
    [Parameter()][string]$SecretKey = "",
    [Parameter()][switch]$SkipServiceInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Cores para output
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

# Verificar se está executando como administrador
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Verificar pré-requisitos
function Test-Prerequisites {
    Write-Info "Verificando pré-requisitos..."
    
    # Verificar Python
    try {
        $pythonVersion = & $PythonPath --version 2>&1
        Write-Success "Python encontrado: $pythonVersion"
    } catch {
        Write-Error "Python não encontrado. Instale Python 3.12+ e adicione ao PATH."
        exit 1
    }
    
    # Verificar pip
    try {
        $pipVersion = & $PythonPath -m pip --version 2>&1
        Write-Success "pip encontrado: $pipVersion"
    } catch {
        Write-Error "pip não encontrado. Instale pip e tente novamente."
        exit 1
    }
    
    # Verificar NSSM (se necessário)
    if (-not $SkipServiceInstall) {
        $nssmFound = $false
        try {
            $null = & $NSSMPath version 2>&1
            $nssmFound = $true
            Write-Success "NSSM encontrado: $NSSMPath"
        } catch {
            if ($InstallNSSM) {
                Write-Warning "NSSM não encontrado. Tentando baixar e instalar..."
                Install-NSSM
            } else {
                Write-Error "NSSM não encontrado. Instale NSSM ou use -InstallNSSM para instalação automática."
                exit 1
            }
        }
    }
}

# Instalar NSSM
function Install-NSSM {
    Write-Info "Baixando NSSM..."
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $tempDir = Join-Path $env:TEMP "nssm_install"
    $zipPath = Join-Path $tempDir "nssm.zip"
    
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        Invoke-WebRequest -Uri $nssmUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
        
        $nssmExe = Get-ChildItem -Path $tempDir -Recurse -Filter "nssm.exe" | Select-Object -First 1
        if ($nssmExe) {
            $nssmTarget = Join-Path $env:ProgramFiles "NSSM\nssm.exe"
            New-Item -ItemType Directory -Path (Split-Path $nssmTarget) -Force | Out-Null
            Copy-Item $nssmExe.FullName $nssmTarget -Force
            $script:NSSMPath = $nssmTarget
            Write-Success "NSSM instalado em: $nssmTarget"
        } else {
            throw "nssm.exe não encontrado no arquivo baixado"
        }
    } catch {
        Write-Error "Falha ao baixar/instalar NSSM: $_"
        exit 1
    } finally {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Instalar dependências Python
function Install-Dependencies {
    Write-Info "Instalando dependências Python..."
    
    $requirementsPath = Join-Path $ProjectPath "requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        Write-Error "Arquivo requirements.txt não encontrado em: $ProjectPath"
        exit 1
    }
    
    try {
        & $PythonPath -m pip install --upgrade pip
        & $PythonPath -m pip install -r $requirementsPath
        Write-Success "Dependências instaladas com sucesso"
    } catch {
        Write-Error "Falha ao instalar dependências: $_"
        exit 1
    }
}

# Criar diretórios necessários
function Initialize-Directories {
    Write-Info "Criando diretórios necessários..."
    
    $directories = @(
        "db",
        "media",
        "media\fichas",
        "media\pedidos",
        "backups"
    )
    
    foreach ($dir in $directories) {
        $fullPath = Join-Path $ProjectPath $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            Write-Success "Diretório criado: $dir"
        } else {
            Write-Info "Diretório já existe: $dir"
        }
    }
}

# Criar arquivo .env
function Initialize-EnvFile {
    if (-not $CreateEnvFile) {
        return
    }
    
    Write-Info "Criando arquivo .env..."
    
    $envPath = Join-Path $ProjectPath ".env"
    if (Test-Path $envPath) {
        Write-Warning "Arquivo .env já existe. Pulando criação."
        return
    }
    
    if ([string]::IsNullOrEmpty($SecretKey)) {
        # Gerar SECRET_KEY aleatória
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        $SecretKey = [Convert]::ToBase64String($bytes)
    }
    
    $envContent = @"
# Configurações da API SGP
ENVIRONMENT=production
SECRET_KEY=$SecretKey
DATABASE_URL=sqlite:///db/banco.db
MEDIA_ROOT=media
MAX_IMAGE_SIZE_MB=10
LOG_LEVEL=INFO
"@
    
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Success "Arquivo .env criado em: $envPath"
    Write-Warning "IMPORTANTE: Revise e ajuste as configurações no arquivo .env conforme necessário!"
}

# Instalar serviço Windows
function Install-WindowsService {
    if ($SkipServiceInstall) {
        Write-Info "Pulando instalação do serviço (--SkipServiceInstall)"
        return
    }
    
    Write-Info "Instalando serviço Windows: $ServiceName"
    
    # Verificar se serviço já existe
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Warning "Serviço $ServiceName já existe. Parando e removendo..."
        Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue
        & $NSSMPath remove $ServiceName confirm
        Start-Sleep -Seconds 2
    }
    
    # Determinar comando baseado na escolha
    if ($UseHypercorn) {
        if ($Workers -gt 0) {
            $appArgs = "-m hypercorn main:app --bind 0.0.0.0:$Port --workers $Workers --loop asyncio"
        } else {
            Write-Warning "Workers=0 mas UseHypercorn=true. Usando 1 worker."
            $appArgs = "-m hypercorn main:app --bind 0.0.0.0:$Port --workers 1 --loop asyncio"
        }
    } else {
        $appArgs = "-m uvicorn main:app --host 0.0.0.0 --port $Port --loop asyncio"
    }
    
    # Instalar serviço
    try {
        & $NSSMPath install $ServiceName $PythonPath $appArgs
        & $NSSMPath set $ServiceName AppDirectory $ProjectPath
        & $NSSMPath set $ServiceName DisplayName "SGP API Server"
        & $NSSMPath set $ServiceName Description "API Sistema de Gestão de Produção (SGP)"
        & $NSSMPath set $ServiceName Start SERVICE_AUTO_START
        & $NSSMPath set $ServiceName AppStdout (Join-Path $ProjectPath "logs\service_stdout.log")
        & $NSSMPath set $ServiceName AppStderr (Join-Path $ProjectPath "logs\service_stderr.log")
        
        # Criar diretório de logs
        $logsDir = Join-Path $ProjectPath "logs"
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
        
        Write-Success "Serviço instalado com sucesso"
        Write-Info "Comando: $PythonPath $appArgs"
    } catch {
        Write-Error "Falha ao instalar serviço: $_"
        exit 1
    }
}

# Iniciar serviço
function Start-WindowsService {
    if ($SkipServiceInstall) {
        Write-Info "Pulando inicialização do serviço"
        return
    }
    
    Write-Info "Iniciando serviço: $ServiceName"
    
    try {
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 3
        
        $service = Get-Service -Name $ServiceName
        if ($service.Status -eq "Running") {
            Write-Success "Serviço iniciado com sucesso"
            Write-Info "Status: $($service.Status)"
            Write-Info "API disponível em: http://0.0.0.0:$Port"
            Write-Info "Documentação: http://localhost:$Port/docs"
        } else {
            Write-Warning "Serviço não está rodando. Status: $($service.Status)"
            Write-Info "Verifique os logs em: $ProjectPath\logs\"
        }
    } catch {
        Write-Error "Falha ao iniciar serviço: $_"
        Write-Info "Tente iniciar manualmente: Start-Service -Name $ServiceName"
    }
}

# Função principal
function Main {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Deploy Automatizado - API SGP" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Verificar privilégios de administrador
    if (-not $SkipServiceInstall -and -not (Test-Administrator)) {
        Write-Error "Este script precisa ser executado como Administrador para instalar serviços."
        Write-Info "Execute: Start-Process powershell -Verb RunAs"
        exit 1
    }
    
    # Normalizar caminho do projeto
    $ProjectPath = (Resolve-Path $ProjectPath).Path
    Write-Info "Diretório do projeto: $ProjectPath"
    
    # Verificar se main.py existe
    $mainPy = Join-Path $ProjectPath "main.py"
    if (-not (Test-Path $mainPy)) {
        Write-Error "Arquivo main.py não encontrado em: $ProjectPath"
        exit 1
    }
    
    # Executar etapas
    Test-Prerequisites
    Install-Dependencies
    Initialize-Directories
    Initialize-EnvFile
    Install-WindowsService
    Start-WindowsService
    
    Write-Host ""
    Write-Success "Deploy concluído com sucesso!"
    Write-Host ""
    Write-Info "Próximos passos:"
    Write-Info "1. Verifique os logs em: $ProjectPath\logs\"
    Write-Info "2. Teste a API em: http://localhost:$Port/health"
    Write-Info "3. Acesse a documentação: http://localhost:$Port/docs"
    Write-Info "4. Configure o firewall para permitir conexões na porta $Port"
    Write-Host ""
}

# Executar
try {
    Main
} catch {
    Write-Error "Erro durante o deploy: $_"
    Write-Error $_.ScriptStackTrace
    exit 1
}

